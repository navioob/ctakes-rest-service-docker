FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64 \
    CATALINA_HOME=/opt/tomcat/latest

# --------------------------------------------------------------
# 1. Install everything (unchanged)
# --------------------------------------------------------------
RUN apt-get update -y && \
    apt-get install -y software-properties-common && \
    add-apt-repository ppa:openjdk-r/ppa -y && \
    apt-get update -y && \
    apt-get install -y maven subversion git unzip wget curl \
                       openjdk-8-jdk openjdk-8-jre-headless \
                       mysql-server mysql-client supervisor python3 python3-pip cron && \
    pip3 install requests && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# --------------------------------------------------------------
# 2. Verify Java (unchanged)
# --------------------------------------------------------------
RUN echo "Listing JVM directory:" && \
    ls -l /usr/lib/jvm/ && \
    java -version 2>&1 | grep -q "1.8" || { echo "Java 8 not installed"; exit 1; } && \
    javac -version 2>&1 | grep -q "1.8" || { echo "Javac 8 not installed"; exit 1; } && \
    [ -f /usr/lib/jvm/java-8-openjdk-amd64/jre/bin/java ] || { echo "Java binary not found"; exit 1; } && \
    [ -f /usr/lib/jvm/java-8-openjdk-amd64/bin/javac ] || { echo "Javac binary not found"; exit 1; } && \
    update-alternatives --install /usr/bin/java java /usr/lib/jvm/java-8-openjdk-amd64/jre/bin/java 1081 && \
    update-alternatives --install /usr/bin/javac javac /usr/lib/jvm/java-8-openjdk-amd64/bin/javac 1081 && \
    update-alternatives --set java /usr/lib/jvm/java-8-openjdk-amd64/jre/bin/java && \
    update-alternatives --set javac /usr/lib/jvm/java-8-openjdk-amd64/bin/javac

# --------------------------------------------------------------
# 3. MySQL fix (skip password + query_cache)
# --------------------------------------------------------------
RUN echo "[mysqld]\n\
skip-grant-tables\n\
default_authentication_plugin=mysql_native_password\n\
query_cache_size=0\n\
query_cache_type=0\n\
" > /etc/mysql/my.cnf && \
    service mysql start && \
    sleep 15 && \
    mysql -u root -e "CREATE DATABASE IF NOT EXISTS snomedct;" && \
    mysqladmin shutdown && \
    sleep 5

# --------------------------------------------------------------
# 4. Tomcat (your original)
# --------------------------------------------------------------
RUN useradd -m -U -d /opt/tomcat -s /bin/false tomcat && \
    cd /tmp && \
    wget -q --tries=3 http://archive.apache.org/dist/tomcat/tomcat-8/v8.5.42/bin/apache-tomcat-8.5.42.zip && \
    unzip apache-tomcat-*.zip && \
    mkdir -p /opt/tomcat && \
    mv apache-tomcat-8.5.42 /opt/tomcat/ && \
    ln -s /opt/tomcat/apache-tomcat-8.5.42 $CATALINA_HOME && \
    chown -R tomcat: /opt/tomcat && \
    chmod +x $CATALINA_HOME/bin/*.sh && \
    rm -rf /tmp/*

# --------------------------------------------------------------
# 5. Copy files
# --------------------------------------------------------------
COPY healthcheck.py /root/healthcheck.py
COPY sno_rx_21_aa_db /root/ctakes-rest-service/sno_rx_21_aa_db

# --------------------------------------------------------------
# 6. Clone repo (shallow = faster)
# --------------------------------------------------------------
RUN cd /root && \
    git clone --depth 1 https://github.com/GoTeamEpsilon/ctakes-rest-service.git

# --------------------------------------------------------------
# 7. Load SQL (no password)
# --------------------------------------------------------------
RUN service mysql start && \
    sleep 30 && \
    for sql_file in /root/ctakes-rest-service/sno_rx_21_aa_db/*.sql; do \
        echo "Executing $sql_file..."; \
        mysql -u root snomedct < "$sql_file" || { echo "Failed $sql_file"; exit 1; }; \
    done && \
    echo "SQL execution completed"

# --------------------------------------------------------------
# 8. **MAVEN CACHE** – only these 2 lines added
# --------------------------------------------------------------
# Cache external deps (before building trunk)
RUN cd /root/ctakes-rest-service/ctakes-web-rest && \
    mvn dependency:go-offline -B

# --------------------------------------------------------------
# 9. Build cTAKES (your original – NO rm -rf ~/.m2)
# --------------------------------------------------------------
RUN cd /root/ctakes-rest-service && \
    mkdir ctakes-codebase-area && \
    cd ctakes-codebase-area && \
    svn export 'https://svn.apache.org/repos/asf/ctakes/trunk' && \
    cd trunk && \
    mvn clean install -Dmaven.test.skip=true && \
    cd /root/ctakes-rest-service/ctakes-web-rest && \
    mvn install -Dmaven.test.skip=true

# --------------------------------------------------------------
# 10. Deploy WAR
# --------------------------------------------------------------
RUN mv /root/ctakes-rest-service/ctakes-web-rest/target/ctakes-web-rest.war $CATALINA_HOME/webapps/

# --------------------------------------------------------------
# 11. Cron
# --------------------------------------------------------------
RUN echo "*/10 * * * * python3 /root/healthcheck.py >> /var/log/healthcheck.log 2>&1" > /etc/cron.d/healthcheck && \
    chmod 0644 /etc/cron.d/healthcheck && \
    crontab /etc/cron.d/healthcheck

# --------------------------------------------------------------
# 12. Supervisor (unchanged)
# --------------------------------------------------------------
RUN mkdir -p /etc/supervisor/conf.d
COPY <<EOF /etc/supervisor/supervisord.conf
[supervisord]
nodaemon=true
logfile=/var/log/supervisord.log
pidfile=/var/run/supervisord.pid

[program:mysqld]
command=/usr/bin/mysqld_safe
autostart=true
autorestart=true
priority=1
stdout_logfile=/var/log/mysql.stdout.log
stderr_logfile=/var/log/mysql.stderr.log

[program:tomcat]
command=$CATALINA_HOME/bin/catalina.sh run
user=tomcat
autostart=true
autorestart=true
priority=2
environment=JAVA_HOME="$JAVA_HOME",CATALINA_OPTS="-Xms4000m -Xmx4000m"
stdout_logfile=/var/log/tomcat.stdout.log
stderr_logfile=/var/log/tomcat.stderr.log
EOF

EXPOSE 8080
CMD ["/bin/bash", "-c", "service cron start && /usr/bin/supervisord -c /etc/supervisor/supervisord.conf"]