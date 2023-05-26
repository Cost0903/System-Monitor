# 1. SysMo 安裝操作文件

## 1.1. ServerSide - 安裝步驟

### 1.1.1. 環境設置

#### 1.1.1.1. 建立相關目錄

```shell
sudo mkdir -p /etc/sysmo/
sudo mkdir -p /opt/sysmo/
sudo mkdir -p /var/log/sysmo/
```

#### 1.1.1.2. 設定防火牆

```shell
sudo firewall-cmd --add-port="自行設定"/tcp --permanent
sudo firewall-cmd --add-service=mysql --permanent
sudo firewall-cmd --reload
```

### 1.1.2. 取得安裝所需檔案

#### 1.1.2.1. 取得 sysmo 相關檔案

切換至/opt/目錄

```shell
cd /opt/sysmo/
```

Github 上下載

```shell
git clone https://github.com/Cost0903/System-Monitor.git
```

### 1.1.3. MySQL 安裝 (需確認是否需要 DB 與 Server 分離)

#### 1.1.3.1. 下載 MySQL 檔案並安裝

在終端機輸入 `mysql` 測試是否有 MySQL Server (注意 : MySQL Community Server 版本需要 8.0 以上)

若無：安裝 MySQL Community Server

```shell
wget http://dev.mysql.com/get/Downloads/MySQL-8.0/mysql-"version".rpm-bundle.tar
tar -xvf mysql-"version".rpm-bundle.tar
sudo yum localinstall mysql-community-server-"version".rpm mysql-community-common-"version".rpm mysql-community-client-"version".rpm  mysql-community-client-plugins-"version".rpm mysql-community-libs-"version".rpm mysql-community-libs-compat-"version".rpm
```

#### 1.1.3.2. 開啟 MySQL, 測試狀態

```shell
sudo systemctl enable --now mysqld
sudo systemctl status mysqld
```

#### 1.1.3.3. 創造 root 帳號的密碼

```shell
grep 'temporary password' /var/log/mysqld.log (取得暫時密碼)
sudo mysql_secure_installation
# Enter
# Set root password : Y
# New password : P@ssw0rd
# Re-enter password : P@ssw0rd
# Remove anonymous users : Y
# Disallow root login remotely : Y
# Remove test database and access to it : Y
# Reload privilege tables now : Y
```

#### 1.1.3.4. 登入並創造資料庫及帳號

```shell
mysql -u root -p
#Enter password
```

登入後輸入

```mysql
CREATE DATABASE log_db;
CREATE USER 'sysmo'@'#ip_address' IDENTIFIED BY '#password';
GRANT ALL PRIVILEGES ON logdb.* TO 'sysmo'@'#ip_address';
```

### 1.1.4. 系統校時

#### 1.1.4.1. 系統安裝校時 & 設定

新增 server "Time Server ip address" iburst 至 chrony 設定檔

```shell
sudo dnf install chrony -y
sudo vim /etc/chrony.conf
```

#### 1.1.4.2. 開啟 Chrony, 測試狀態

```
systemctl enable --now chronyd
systemctl status chronyd
chronyc tracking
```

#### 1.1.5 安裝 pip requirements

如有使用虛擬環境請先切換至特定環境 (注意 : 目前使用 Python 版本為 Python 3.10.7)

```shell
python3 -m pip install -r requirements.txt
```

### 1.1.6. 開啟 Server

#### 1.1.6.1. 確認連接 Mysql Server 需要的參數

```shell
vim /etc/sysmo/server_db.conf
# 更改以下參數
NAME = logdb       # Database 名稱
HOST = 127.0.0.1    # MySQL Server 連線 IP
PORT = 3306         # 預設 Port 可更改
USER = sysmo        # 資料庫使用者名稱
PASSWORD = password # 密碼原則請根據公司規定自行設置
```

#### 1.1.6.2. 新建 Tables

```shell
cd /opt/System-Monitor/sysmo/
python3 manage.py makemigrations
python3 manage.py migrate
```

#### 1.1.6.3. 新增 admin 使用者

```shell
cd /opt/sysmo/server/logserver
python3 manage.py createsuperuser
```

#### 1.1.6.4. 修改設定檔

修改 Server 設定

```shell
vim /etc/sysmo/server.conf
[logrotate]
INTERVAL = 180              # Agent 預設監控間隔

[DEFAULT_POLICY]
DEFAULT_MAJOR = 80          # 監控指標 Major 預設值
DEFAULT_WARNING = 90        # 監控指標 Warning 預設值
DEFAULT_CRITICAL = 95       # 監控指標 Critical 預設值
DEFAULT_OFFLINE_TIME = 2    # 監控指標 Offline 預設值 : INTERVAL * DEFAULT_OFFLINE_TIME

[SWAP_POLICY]               # 獨立設置各項指標的預設值 (未完成) 預計為 CPU, Memroy, Swap, Disk 分開
SWAP_WARNING = 60
SWAP_MAJOR = 80
SWAP_CRITICAL = 90

[DISK_POLICY]
DISK_MAJOR = 90
DISK_WARNING = 80
DISK_CRITICAL = 97

[MODE]
DEBUG_MODE = 1              # 開啟後會紀錄 debug 標籤的訊息

[mail-config]
SWITCH = 1                  # 1 為開啟寄信功能
HOST = smtp.gmail.com
PORT = 587
USE_TLS = True
USER = user@gmail.com
PASSWORD = password
```

#### 1.1.6.5. 修改 uwsgi 檔案

```shell
[uwsgi]
uid = nginx                                         # 使嗽 nginx 做為 User，可自行修改
chdir = /opt/sysmo/sysmo             #
socket = /opt/sysmo/sysmo.sock
home = /opt/sysmo/.venv
module = sysmo.wsgi:application
master = True
processes = 4
threads = 4
vacuum = True
```

#### 1.1.6.6. 修改 Nginx 設定檔

建立目錄

```shell
sudo mkdir -p /etc/nginx/sites-available
sudo mkdir -p /etc/nginx/sites-enabled
```

修改 nginx.conf

```shell
# include /etc/nginx/conf.d/*.conf;
include /etc/nginx/sites-enabled/*;
```

修改 sysmo-uwsgi.conf，請根據伺服器內目錄位置自行調整

```shell
upstream django {
	server unix:////opt/sysmo/sysmo.sock;
}


server {
        listen 80;
        server_name _;
        charset utf-8;

        client_max_body_size 75M;

        location / {
        	include /opt/sysmo/uwsgi_params;
		uwsgi_pass django;
		add_header Access-Control-Allow-Origin http://192.168.1.138;
	}
        location /static {
                alias /opt/sysmo/sysmo/static/;
        }

}

```

#### 1.1.6.7. 開啟服務

```shell
sudo systemctl enable --now nginx.service
sudo systemctl enable --now sysmo.service
```

## 1.2. ClientSide - 環境&註冊

### 1.2.1. 環境設置

#### 1.2.1.1. 建立相關目錄

```shell
sudo mkdir -p /etc/sysmo-agent # 存放設定檔
sudo mkdir -p /opt/sysmo-agent # 執行檔存放位置
sudo mkdir -p /var/log/sysmo-agent # Log 檔案存放位置
```

### 1.2.2. 系統校時

#### 1.2.2.1. 系統安裝校時 & 設定

新增 server "Time Server ip address" iburst 至 chrony 設定檔

```shell
sudo dnf install chrony -y
sudo vim /etc/chrony.conf
```

#### 1.2.2.2. 開啟 Chrony, 測試狀態

```shell
systemctl enable --now chronyd
systemctl status chronyd
chronyc tracking
```

### 1.2.3. 取得所需檔案

#### 1.2.3.1. 取得 sysmo-agent

需下載 sysmo-agent, sysmo-agent.conf, sysmo-agent.service (包含在 Github 上)

```shell
git clone https://github.com/Cost0903/System-Monitor.git
```

#### 1.2.3.2. 將檔案放置特定目錄

```shell
cp sysmo-agent /opt/sysmo-agent/
cp sysmo-agent.conf /etc/sysmo-agent/
sudo cp sysmo-agent.service /usr/lib/systemd/system/
sudo systemctl daemon-reload
```

### 1.2.4. 參數設定

#### 1.2.4.1. 修改 Config 設定

```shell
vim /etc/sysmo-agent/sysmo-agent.conf
[Interval]
Perform = 180 # 目前此參數無法自行設定，修改網頁上 interval 後會自行更改並重啟 Agent 以便生效

[Server]
# 使用的 IP:Port 可自行設定
Host = 192.168.1.138
Port = 9090
```

### 1.2.5. 開啟服務

#### 1.2.5.1. 開啟 sysmo-agent.service 並檢查

```shell
sudo systemctl enable --now sysmo-agent.service
systemctl status sysmo-agent.service
```

### 1.2.6. Log 確認

#### 1.2.6.1. Log 內容確認

```shell
# /var/log/sysmo-agent/agent.log
tail -f /var/log/sysmo-agent/agent.log
```

#### 額外參考資料

#### PyInstaller 打包

如 Agent 有進行修改，需重新打包成 exe 檔案

```shell
pyinstaller -F sysmo-agent.py
```
