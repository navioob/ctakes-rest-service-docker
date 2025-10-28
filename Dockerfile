FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64 \
    CATALINA_HOME=/opt/tomcat/latest

# --------------------------------------------------------------
# 1. Install everything
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
# 2. Verify Java
# --------------------------------------------------------------
RUN echo "Listing JVM directory:" && \
    ls -l /usr/lib/jvm/ && \
    java -version 2>&1 | grep -q "1.8" || exit 1 && \
    javac -version 2>&1 | grep -q "1.8" || exit 1 && \
    update-alternatives --install /usr/bin/java java /usr/lib/jvm/java-8-openjdk-amd64/jre/bin/java 1081 && \
    update-alternatives --install /usr/bin/javac javac /usr/lib/jvm/java-8-openjdk-amd64/bin/javac 1081 && \
    update-alternatives --set java /usr/lib/jvm/java-8-openjdk-amd64/jre/bin/java && \
    update-alternatives --set javac /usr/lib/jvm/java-8-openjdk-amd64/bin/javac

# --------------------------------------------------------------
# 3. FIXED: Create mysql user + config + init DB
# --------------------------------------------------------------
RUN groupadd -r mysql && \
    useradd -r -g mysql -d /var/lib/mysql -s /usr/sbin/nologin mysql && \
    mkdir -p /var/lib/mysql /var/run/mysqld && \
    chown mysql:mysql /var/lib/mysql /var/run/mysqld && \
    echo "[mysqld]\n\
skip-grant-tables\n\
default_authentication_plugin=mysql_native_password\n\
query_cache_size=0\n\
query_cache_type=0\n\
datadir=/var/lib/mysql\n\
socket=/var/run/mysqld/mysqld.sock\n\
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
    chmod +x $CATALINA_HOME/bin/*.sh &&