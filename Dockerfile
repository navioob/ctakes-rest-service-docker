# Use Ubuntu 18.04 as the base image
FROM ubuntu:18.04

# Set non-interactive mode for apt-get
ENV DEBIAN_FRONTEND=noninteractive

# Add the OpenJDK PPA to ensure Java 8 availability
RUN apt-get update -y && \
    apt-get install -y software-properties-common && \
    add-apt-repository ppa:openjdk-r/ppa && \
    apt-get update -y && \
    apt-get install -y maven subversion git unzip wget curl openjdk-8-jdk openjdk-8-jre-headless mysql-server mysql-client supervisor && \
    apt-get clean

# Verify Java 8 installation and configure alternatives for ARM64
RUN echo "Listing JVM directory:" && \
    ls -l /usr/lib/jvm/ && \
    java -version 2>&1 | grep -q "1.8" || { echo "Java 8 not installed"; exit 1; } && \
    javac -version 2>&1 | grep -q "1.8" || { echo "Javac 8 not installed"; exit 1; } && \
    [ -f /usr/lib/jvm/java-8-openjdk-arm64/jre/bin/java ] || { echo "Java binary not found"; exit 1; } && \
    [ -f /usr/lib/jvm/java-8-openjdk-arm64/bin/javac ] || { echo "Javac binary not found"; exit 1; } && \
    update-alternatives --install /usr/bin/java java /usr/lib/jvm/java-8-openjdk-arm64/jre/bin/java 1081 && \
    update-alternatives --install /usr/bin/javac javac /usr/lib/jvm/java-8-openjdk-arm64/bin/javac 1081 && \
    update-alternatives --set java /usr/lib/jvm/java-8-openjdk-arm64/jre/bin/java && \
    update-alternatives --set javac /usr/lib/jvm/java-8-openjdk-arm64/bin/javac && \
    update-alternatives --display java && \
    update-alternatives --display javac

# Initialize MySQL and set root password
RUN service mysql start && \
    sleep 10 && \
    # Use mysqld_safe to ensure MySQL starts in a mode allowing root access
    mysqld_safe --skip-grant-tables & \
    sleep 10 && \
    # Create a temporary SQL script to set root password
    echo "ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'pass'; FLUSH PRIVILEGES;" > /tmp/init.sql && \
    mysql -u root < /tmp/init.sql && \
    # Verify root access with new password
    mysql -u root -ppass -e "SELECT 1;" || { echo "Root access with password failed"; exit 1; } && \
    # Mimic mysql_secure_installation steps
    mysql -u root -ppass -e "DELETE FROM mysql.user WHERE User='';" && \
    mysql -u root -ppass -e "DELETE FROM mysql.user WHERE User='root' AND Host NOT IN ('localhost', '127.0.0.1', '::1');" && \
    mysql -u root -ppass -e "DROP DATABASE IF EXISTS test;" && \
    mysql -u root -ppass -e "DELETE FROM mysql.db WHERE Db='test' OR Db='test\\_%';" && \
    mysql -u root -ppass -e "FLUSH PRIVILEGES;" && \
    # Clean up and stop MySQL
    rm /tmp/init.sql && \
    mysqladmin -u root -ppass shutdown && \
    sleep 5

# Install Tomcat 8.5.42
RUN useradd -m -U -d /opt/tomcat -s /bin/false tomcat && \
    cd /tmp && \
    wget -q --tries=3 http://archive.apache.org/dist/tomcat/tomcat-8/v8.5.42/bin/apache-tomcat-8.5.42.zip && \
    unzip apache-tomcat-*.zip && \
    mkdir -p /opt/tomcat && \
    mv apache-tomcat-8.5.42 /opt/tomcat/ && \
    ln -s /opt/tomcat/apache-tomcat-8.5.42 /opt/tomcat/latest && \
    chown -R tomcat: /opt/tomcat && \
    chmod +x /opt/tomcat/latest/bin/*.sh && \
    rm -rf /tmp/*

# Clone the repository
RUN cd /root && \
    git clone https://github.com/GoTeamEpsilon/ctakes-rest-service.git && \
    cd ctakes-rest-service

# Load SQL data scripts (this may take several hours)
RUN service mysql start && \
    sleep 10 && \
    mysql -u root -ppass < /root/ctakes-rest-service/sno_rx_16ab_db/01_setup.sql && \
    mysql -u root -ppass < /root/ctakes-rest-service/sno_rx_16ab_db/02_load.sql && \
    mysql -u root -ppass < /root/ctakes-rest-service/sno_rx_16ab_db/03_load.sql && \
    mysql -u root -ppass < /root/ctakes-rest-service/sno_rx_16ab_db/04_load.sql && \
    mysql -u root -ppass < /root/ctakes-rest-service/sno_rx_16ab_db/05_load.sql && \
    mysql -u root -ppass < /root/ctakes-rest-service/sno_rx_16ab_db/06_load.sql && \
    mysql -u root -ppass < /root/ctakes-rest-service/sno_rx_16ab_db/07_load.sql && \
    mysql -u root -ppass < /root/ctakes-rest-service/sno_rx_16ab_db/08_load.sql && \
    service mysql stop

# Build the codebase
RUN cd /root/ctakes-rest-service && \
    mkdir ctakes-codebase-area && \
    cd ctakes-codebase-area && \
    # Check out cTAKES trunk
    svn export 'https://svn.apache.org/repos/asf/ctakes/trunk' && \
    cd trunk && \
    # Clean Maven cache to avoid corrupted artifacts
    rm -rf ~/.m2/repository && \
    # Build all cTAKES modules to generate 4.0.1-SNAPSHOT artifacts
    mvn install -Dmaven.test.skip=true -U -Dmaven.repo.local=/root/.m2/repository && \
    cd ../../ctakes-web-rest && \
    # Build ctakes-web-rest
    mvn install -Dmaven.test.skip=true -U -Dmaven.repo.local=/root/.m2/repository

# Deploy the WAR file to Tomcat
RUN mv /root/ctakes-rest-service/ctakes-web-rest/target/ctakes-web-rest.war /opt/tomcat/latest/webapps/

# Set up Supervisor to manage MySQL and Tomcat
RUN mkdir -p /etc/supervisor/conf.d
COPY <<EOF /etc/supervisor/supervisord.conf
[supervisord]
nodaemon=true
logfile=/var/log/supervisord.log
pidfile=/var/run/supervisord.pid

[program:mysqld]
command=/usr/sbin/mysqld --user=root
autostart=true
autorestart=true
priority=1
stdout_logfile=/var/log/mysql.stdout.log
stderr_logfile=/var/log/mysql.stderr.log

[program:tomcat]
command=/opt/tomcat/latest/bin/catalina.sh run
user=tomcat
autostart=true
autorestart=true
priority=2
environment=JAVA_HOME="/usr/lib/jvm/java-8-openjdk-arm64",JAVA_OPTS="-Djava.security.egd=file:///dev/urandom",CATALINA_HOME="/opt/tomcat/latest",CATALINA_BASE="/opt/tomcat/latest",CATALINA_OPTS="-Xms4000m -Xmx4000m -server -XX:+UseParallelGC"
stdout_logfile=/var/log/tomcat.stdout.log
stderr_logfile=/var/log/tomcat.stderr.log
EOF

# Expose Tomcat port
EXPOSE 8080

# Run Supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]