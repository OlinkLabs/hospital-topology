import paramiko
import time

# Datos de conexión al Palo Alto PA-VM
hostname = "5.0.10.30"
port = 22
username = "admin"
password = "Admin@123"

commands = """
configure

# Sub-interfaces en ethernet1/3
set network interface ethernet ethernet1/3 layer3 units ethernet1/3.10 tag 10
set network interface ethernet ethernet1/3 layer3 units ethernet1/3.10 ip 10.0.10.1/24

set network interface ethernet ethernet1/3 layer3 units ethernet1/3.20 tag 20
set network interface ethernet ethernet1/3 layer3 units ethernet1/3.20 ip 10.0.20.1/24

set network interface ethernet ethernet1/3 layer3 units ethernet1/3.30 tag 30
set network interface ethernet ethernet1/3 layer3 units ethernet1/3.30 ip 10.0.30.1/24

# Interfaces físicas DMZ e Internet
set network interface ethernet ethernet1/1 layer3 ip 10.0.200.20/24
set network interface ethernet ethernet1/2 layer3 dhcp-client enable yes

# Crear zonas
set zone GESTION  network layer3 ethernet1/3.10
set zone CAMARAS  network layer3 ethernet1/3.20
set zone MEDICOS  network layer3 ethernet1/3.30
set zone DMZ      network layer3 ethernet1/1
set zone untrust  network layer3 ethernet1/2

# Objetos de dirección
set address VLAN10_NET ip-netmask 10.0.10.0/24
set address VLAN20_NET ip-netmask 10.0.20.0/24
set address VLAN30_NET ip-netmask 10.0.30.0/24
set address DMZ_NET    ip-netmask 10.0.200.0/24
set address WEB_DMZ    ip-netmask 10.0.200.10/32

# Políticas de Seguridad
set rulebase security rules GESTION_to_CAMARAS from GESTION to CAMARAS source VLAN10_NET destination VLAN20_NET application any service any action allow
set rulebase security rules GESTION_to_MEDICINA from GESTION to MEDICOS source VLAN10_NET destination VLAN30_NET application ssh,ssl service application-default action allow
set rulebase security rules CAMARAS_to_MEDICINA from CAMARAS to MEDICOS source VLAN20_NET destination VLAN30_NET application any service any action deny
set rulebase security rules MEDICINA_to_CAMARAS from MEDICOS to CAMARAS source VLAN30_NET destination VLAN20_NET application any service any action deny

set rulebase security rules INTERNAS_to_DMZ from GESTION,CAMARAS,MEDICOS to DMZ source VLAN10_NET,VLAN20_NET,VLAN30_NET destination WEB_DMZ application web-browsing,ssl,ssh service application-default action allow
set rulebase security rules DMZ_to_INTERNAS from DMZ to GESTION,CAMARAS,MEDICOS source DMZ_NET destination VLAN10_NET,VLAN20_NET,VLAN30_NET application any service any action deny

set rulebase security rules INTERNAS_to_INTERNET from GESTION,CAMARAS,MEDICOS to untrust source VLAN10_NET,VLAN20_NET,VLAN30_NET destination any application any service any action allow
set rulebase security rules INTERNET_to_DMZ from untrust to DMZ source any destination WEB_DMZ application web-browsing,ssl service application-default action allow

# NAT Saliente
set rulebase nat rules NAT_Internas_to_Internet from GESTION,CAMARAS,MEDICOS to untrust source VLAN10_NET,VLAN20_NET,VLAN30_NET destination any service any source-translation dynamic-ip-and-port interface-address ethernet1/2

# Commit
commit
exit
"""


def configure_palo_alto():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print("[+] Conectando al Palo Alto PA-VM...")
    client.connect(hostname, port=port, username=username, password=password)

    shell = client.invoke_shell()
    time.sleep(1)
    print("[+] Enviando configuración...")

    for line in commands.strip().split('\n'):
        if not line.strip().startswith("#") and line.strip():
            shell.send((line + '\n').encode('utf-8'))
            time.sleep(0.5)
            # Se lee el output parcial para no saturar el buffer
            output = shell.recv(5000).decode('utf-8')
            print(output)

    shell.close()
    client.close()
    print("[+] Configuración finalizada.")


if __name__ == "__main__":
    configure_palo_alto()
