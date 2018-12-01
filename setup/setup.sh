#!/bin/sh

#ssh pi@hassbian

sudo passwd root
sudo passwd --unlock root
sudo nano /etc/ssh/sshd_config #PermitRootLogin yes
sudo mkdir /root/.ssh
mkdir ~/.ssh
sudo reboot

#ssh root@hassbian "mkdir ~/.ssh"
#ssh admin@hassbian "mkdir ~/.ssh"
#scp ~/.ssh/authorized_keys root@hassbian:~/.ssh/
#scp ~/.ssh/authorized_keys admin@hassbian:~/.ssh/
#ssh root@hassbian

# Rename pi->admin
usermod -l admin pi
groupmod -n admin pi
mv /home/pi /home/admin
usermod -d /home/admin admin
passwd admin
echo "admin ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

raspi-config # Hostname, WiFi, locales(en_US.UTF-8/zh_CN.GB18030/zh_CN.UTF-8), Timezone

#
apt-get update
apt-get upgrade -y
#apt-get autoclean
#apt-get clean

# Mosquitto
apt-get install mosquitto mosquitto-clients
#echo "allow_anonymous true" >> /etc/mosquitto/mosquitto.conf
#systemctl stop mosquitto
#sleep 2
#rm -rf /var/lib/mosquitto/mosquitto.db
#systemctl start mosquitto
#sleep 2
#mosquitto_sub -v -t '#'

# For HomeKit
apt-get install libavahi-compat-libdnssd-dev

# For Raspbian
apt-get install python3 python3-pip

#update pip
#https://bootstrap.pypa.io/get-pip.py
python3 -m pip install --upgrade pip setuptools wheel

# Install PIP 18
##python3 -m pip install --upgrade pip # Logout after install
#curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
#python3 get-pip.py --force-reinstall

# For Armbian
echo "Asia/Shanghai" > /etc/timezone && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime
apt-get install python3-pip python3-dev libffi-dev python3-setuptools
#Fix 8.8.8.8 DNS rm /etc/resolvconf/resolv.conf.d/head && touch /etc/resolvconf/resolv.conf.d/head && rm /etc/resolvconf/resolv.conf.d/base && touch /etc/resolvconf/resolv.conf.d/base && systemctl restart network-manager.service
#systemctl stop lircd.service lircd-setup.service lircd.socket lircd-uinput.service lircmd.service
#apt remove -y lirc && apt autoremove -y

# Home Assistant
pip3 install wheel netdisco xmltodict aiohttp_cors
pip3 install homeassistant
#pip3 install pycryptodome #https://github.com/home-assistant/home-assistant/issues/12675

# Auto start
cat <<EOF > /etc/systemd/system/homeassistant.service
[Unit]
Description=Home Assistant
After=network-online.target

[Service]
Type=simple
User=admin
ExecStart=/usr/local/bin/hass

[Install]
WantedBy=multi-user.target

EOF

# Appdaemon
cat <<EOF > /etc/systemd/system/appdaemon.service
[Unit]
Description=App Daemon
After=network-online.target

[Service]
Type=simple
User=admin
ExecStart=/usr/local/bin/appdaemon

[Install]
WantedBy=multi-user.target

EOF

systemctl --system daemon-reload
systemctl enable homeassistant
systemctl start homeassistant

systemctl enable appdaemon
systemctl start appdaemon

# Switch to admin

# Debug
hass

# Restart
echo .> /var/log/daemon.log; echo .>~/.homeassistant/home-assistant.log; systemctl restart homeassistant; tail -f /var/log/daemon.log

# Upgrage
systemctl stop homeassistant
pip3 install --upgrade homeassistant
systemctl start homeassistant

# Samba
apt-get install samba
smbpasswd -a root

cat <<EOF > /etc/samba/smb.conf
[global]
workgroup = WORKGROUP
wins support = yes
dns proxy = no
log file = /var/log/samba/log.%m
max log size = 1000
syslog = 0
panic action = /usr/share/samba/panic-action %d
server role = standalone server
passdb backend = tdbsam
obey pam restrictions = yes
unix password sync = yes
passwd program = /usr/bin/passwd %u
passwd chat = *Enter\snew\s*\spassword:* %n\n *Retype\snew\s*\spassword:* %n\n *password\supdated\ssuccessfully* .
pam password change = yes
map to guest = bad user
usershare allow guests = yes

[homes]
comment = Home Directories
browseable = no
create mask = 0700
directory mask = 0700
valid users = %S

[hass]
path = /root/.homeassistant
valid users = root
browseable = yes
writable = yes

EOF
/etc/init.d/samba restart

cat <<\EOF >> /root/.bashrc
alias ls='ls $LS_OPTIONS'
alias ll='ls $LS_OPTIONS -l'
alias l='ls $LS_OPTIONS -lA'
alias rmqtt='systemctl stop mosquitto; sleep 2; rm -rf /var/lib/mosquitto/mosquitto.db; systemctl start mosquitto'
alias upha='systemctl stop homeassistant; pip3 install homeassistant --upgrade; systemctl start homeassistant'
alias reha='systemctl restart homeassistant'
EOF

mkdir /media/sda1
cat <<\EOF > /etc/fstab
/dev/sda1 /media/sda1 hfsplus ro,sync,noexec,nodev,noatime,nodiratime 0 0
EOF

apt-get install samba
