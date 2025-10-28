# --------------------------------------------------------------
#  FAST cTAKES REST SERVICE – Ubuntu 22.04
# --------------------------------------------------------------
FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64

# 1. Install build tools (Java 8 is in the default repos – no PPA)
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
        openjdk-8-jdk maven git subversion unzip wget curl python3-pip && \
    pip3 install --no-cache-dir requests && \
    rm -rf /var/lib/apt/lists/*

# 2. Clone the repo (shallow – faster)
WORKDIR /build
RUN git clone --depth 1 https://github.com/GoTeamEpsilon/ctakes-rest-service.git

# 3. Cache Maven dependencies (uses the two real pom.xml files)
RUN cd ctakes-rest-service/ctakes-codebase-area/trunk && \
    mvn dependency:go-offline -B && \
    cd ../../ctakes-web-rest && \
    mvn dependency:go-offline -B

# 4. Build only what we need
RUN cd ctakes-rest-service && \
    mkdir -p ctakes-codebase-area && \
    cd ctakes-codebase-area && \
    svn export --depth files https://svn.apache.org/repos/asf/ctakes/trunk && \
    cd trunk && \
    mvn clean install -Dmaven.test.skip=true -B && \
    cd /build/ctakes-rest-service/ctakes-web-rest && \
    mvn install -Dmaven.test.skip=true -B

# --------------------------------------------------------------
#  FINAL RUNTIME IMAGE
# --------------------------------------------------------------
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64 \
    CATALINA_HOME=/opt/tomcat

# Runtime only
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
        openjdk-8-jre-headless mysql-server supervisor cron ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Tomcat 8.5.42 (download + extract in one step)
RUN useradd -m -d /opt/tomcat tomcat && \
    wget -qO- http://archive.apache.org/dist/tomcat/tomcat-8/v8.5.42/bin/apache-tomcat-8.5.42.tar.gz | \
    tar -xz -C /opt && \
    mv /opt/apache-tomcat-8.5.42 $CATALINA_HOME && \
    chown -R tomcat:tomcat $CATALINA_HOME && \
    ln -s $CATALINA_HOME /opt/tomcat-latest

# Copy WAR, SQL files, health-check script
COPY --from=builder /build/ctakes-rest-service/ctakes-web-rest/target/ctakes-web-rest.war $CATALINA_HOME/webapps/
COPY sno_rx_21_aa_db /sno_rx_21_aa_db
COPY healthcheck.py /root/healthcheck.py

# MySQL 8.0 compatibility (no password, query_cache off)
RUN echo "[mysqld]\n\
skip-grant-tables\n\
default_authentication_plugin=mysql_native_password\n\
query_cache_size=0\n\
query_cache_type=0\n\
" > /etc/mysql/my.cnf

# Load dictionary at **build time**
RUN service mysql start && \
    sleep 10 && \
    mysql -u root -e "CREATE DATABASE IF NOT EXISTS snomedct;" && \
    for f in /sno_rx_21_aa_db/*.sql; do \
        mysql -u root snomedct < "$f"; \
    done && \
    mysqladmin shutdown

# Cron health-check (every 10 min)
RUN echo "*/10 * * * * python3 /root/healthcheck.py >> /var/log/healthcheck.log 2>&1" > /etc/cron.d/healthcheck && \
    chmod 0644 /etc/cron.d/healthcheck && crontab /etc/cron.d/healthcheck

# Supervisor
COPY <<EOF /etc/supervisor/conf.d/all.conf
[supervisord]
nodaemon=true
logfile=/var/log/supervisord.log

[program:mysql]
command=/usr/bin/mysqld_safe
autostart=true
autorestart=true
stdout_logfile=/var/log/mysql.stdout.log
stderr_logfile=/var/log/mysql.stderr.log

[program:tomcat]
command=$CATALINA_HOME/bin/catalina.sh run
user=tomcat
autostart=true
autorestart=true
environment=JAVA_OPTS="-Xms2g -Xmx3g"
stdout_logfile=/var/log/tomcat.stdout.log
stderr_logfile=/var/log/tomcat.stderr.log
EOF

EXPOSE 8080
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/all.conf"]