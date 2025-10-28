# --------------------------------------------------------------
#  FAST cTAKES REST SERVICE – Ubuntu 22.04 (Tomcat = old style)
# --------------------------------------------------------------
FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64

# 1. Install build tools (Java 8 is in Ubuntu 22.04 – no PPA)
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
        openjdk-8-jdk maven git subversion unzip wget curl python3-pip && \
    pip3 install --no-cache-dir requests && \
    rm -rf /var/lib/apt/lists/*

# 2. Clone repo (shallow)
WORKDIR /build
RUN git clone --depth 1 https://github.com/GoTeamEpsilon/ctakes-rest-service.git

# 3. Cache Maven deps from real pom.xml files
RUN cd ctakes-rest-service/ctakes-codebase-area/trunk && \
    mvn dependency:go-offline -B || true && \
    cd ../../ctakes-web-rest && \
    mvn dependency:go-offline -B

# 4. Build cTAKES
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

# Runtime deps (wget + unzip now included)
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
        openjdk-8-jre-headless mysql-server supervisor cron ca-certificates \
        wget unzip && \
    rm -rf /var/lib/apt/lists/*

# === TOMCAT: OLD STYLE (same as your original) ===
RUN useradd -m -U -d /opt/tomcat -s /bin/false tomcat && \
    cd /tmp && \
    wget -q --tries=3 http://archive.apache.org/dist/tomcat/tomcat-8/v8.5.42/bin/apache-tomcat-8.5.42.zip && \
    unzip apache-tomcat-*.zip && \
    mkdir -p /opt/tomcat && \
    mv apache-tomcat-8.5.42 /opt/tomcat/ && \
    ln -s /opt/tomcat/apache-tomcat-8.5.42 $CATALINA_HOME && \
    chown -R tomcat:tomcat /opt/tomcat && \
    chmod +x $CATALINA_HOME/bin/*.sh && \
    rm -rf /tmp/*

# Copy WAR, SQL, health-check
COPY --from=builder /build/ctakes-rest-service/ctakes-web-rest/target/ctakes-web-rest.war $CATALINA_HOME/webapps/
COPY sno_rx_21_aa_db /sno_rx_21_aa_db
COPY healthcheck.py /root/healthcheck.py

# MySQL 8.0 fix
RUN echo "[mysqld]\n\
skip-grant-tables\n\
default_authentication_plugin=mysql_native_password\n\
query_cache_size=0\n\
query_cache_type=0\n\
" > /etc/mysql/my.cnf

# Load dictionary at build time
RUN service mysql start && \
    sleep 10 && \
    mysql -u root -e "CREATE DATABASE IF NOT EXISTS snomedct;" && \
    for f in /sno_rx_21_aa_db/*.sql; do \
        mysql -u root snomedct < "$f"; \
    done && \
    mysqladmin shutdown

# Health check cron
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