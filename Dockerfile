FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64

# 1. Install deps + Java 8 (NO PPA — use default Ubuntu 22.04 Java 8)
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
        openjdk-8-jdk maven git svn unzip wget curl python3-pip && \
    pip3 install requests && \
    rm -rf /var/lib/apt/lists/*

# 2. Cache Maven deps (HUGE speedup)
WORKDIR /build
COPY pom.xml ./
RUN mvn dependency:go-offline -B

# 3. Clone & build cTAKES (only what we need)
RUN git clone --depth 1 https://github.com/GoTeamEpsilon/ctakes-rest-service.git && \
    cd ctakes-rest-service && \
    mkdir ctakes-codebase-area && \
    cd ctakes-codebase-area && \
    svn export --depth files https://svn.apache.org/repos/asf/ctakes/trunk && \
    cd trunk && \
    mvn clean install -Dmaven.test.skip=true -B && \
    cd /build/ctakes-rest-service/ctakes-web-rest && \
    mvn install -Dmaven.test.skip=true -B

# Final stage
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64 \
    CATALINA_HOME=/opt/tomcat

# Install runtime only
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
        openjdk-8-jre-headless mysql-server supervisor cron ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Tomcat
RUN useradd -m -d /opt/tomcat tomcat && \
    wget -qO- http://archive.apache.org/dist/tomcat/tomcat-8/v8.5.42/bin/apache-tomcat-8.5.42.tar.gz | \
    tar -xz -C /opt && \
    mv /opt/apache-tomcat-8.5.42 $CATALINA_HOME && \
    chown -R tomcat:tomcat $CATALINA_HOME && \
    ln -s $CATALINA_HOME /opt/tomcat-latest

# Copy WAR + SQL + scripts
COPY --from=builder /build/ctakes-rest-service/ctakes-web-rest/target/ctakes-web-rest.war $CATALINA_HOME/webapps/
COPY sno_rx_21_aa_db /sno_rx_21_aa_db
COPY healthcheck.py /root/healthcheck.py

# MySQL config (fix query_cache)
RUN echo "[mysqld]\nskip-grant-tables\ndefault_authentication_plugin=mysql_native_password\nquery_cache_size=0\n" > /etc/mysql/my.cnf

# Init DB
RUN service mysql start && \
    sleep 10 && \
    mysql -u root -e "CREATE DATABASE snomedct;" && \
    for f in /sno_rx_21_aa_db/*.sql; do mysql -u root snomedct < "$f"; done && \
    mysqladmin shutdown

# Supervisor
COPY <<EOF /etc/supervisor/conf.d/all.conf
[supervisord]
nodaemon=true

[program:mysql]
command=/usr/bin/mysqld_safe
autostart=true
autorestart=true

[program:tomcat]
command=$CATALINA_HOME/bin/catalina.sh run
user=tomcat
autostart=true
autorestart=true
environment=JAVA_OPTS="-Xms2g -Xmx3g"
EOF

# Health check
RUN echo "*/10 * * * * python3 /root/healthcheck.py >> /var/log/healthcheck.log 2>&1" > /etc/cron.d/healthcheck && \
    chmod 0644 /etc/cron.d/healthcheck && crontab /etc/cron.d/healthcheck

EXPOSE 8080
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]