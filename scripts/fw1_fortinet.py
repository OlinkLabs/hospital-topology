import paramiko
import time

# Datos de conexión al FortiGate
hostname = "5.0.10.29"
port = 22
username = "admin"
password = "admin"

# Comandos de configuración completa
commands = """
config system global
    set alias "Forti-Router-Core"
end

# ——————————————————————————
# Interfaces Físicas y VLANs
# ——————————————————————————
# Renombramos interfaces lógicas para alinear eth ↔ portN
config system interface
    edit "port1"
        set mode dhcp
        set allowaccess ping https ssh http fgfm
        set alias "MGMT"
    next
    edit "port2"
        set alias "TRUNK-INTERNAL"
        set role lan
        set vdom "root"
        set type physical
    next
    edit "port3"
        set ip 10.0.200.1 255.255.255.0
        set allowaccess ping
        set alias "DMZ"
        set role dmz
    next
    # Activamos redundancia
    edit "port4"
        set alias "TRUNK-INTERNAL-2"
        set role lan
        set vdom "root"
        set type physical
    next
end

# ——————————————————————————
# Creamos interfaces VLAN sobre port2
# ——————————————————————————
config system interface
    # VLAN 10 (Gestión interna)
    edit "VLAN10"
        set vdom "root"
        set ip 10.0.10.1 255.255.255.0
        set allowaccess ping https ssh
        set interface "port2"
        set vlanid 10
        set role lan
    next
    # VLAN 20 (Cámaras)
    edit "VLAN20"
        set vdom "root"
        set ip 10.0.20.1 255.255.255.0
        set allowaccess ping
        set interface "port2"
        set vlanid 20
        set role lan
    next
    # VLAN 30 (Equipos de medicina)
    edit "VLAN30"
        set vdom "root"
        set ip 10.0.30.1 255.255.255.0
        set allowaccess ping
        set interface "port2"
        set vlanid 30
        set role lan
    next
end

# En un principio no activaremos la redundancia por posibles problemas con FortiOS,
# ya que hacer un trunk idéntico, no se recomienda en dos interfaces físicas sin LACP.

# ——————————————————————————
# Objetos de Dirección (address objects)
# ——————————————————————————
config firewall address
    edit "VLAN10_NET"
        set subnet 10.0.10.0 255.255.255.0
    next
    edit "VLAN20_NET"
        set subnet 10.0.20.0 255.255.255.0
    next
    edit "VLAN30_NET"
        set subnet 10.0.30.0 255.255.255.0
    next
    edit "DMZ_WEBSERVER"
        set subnet 10.0.200.10 255.255.255.255
    next
    edit "DMZ_NET"
        set subnet 10.0.200.0 255.255.255.0
    next
    # En caso de crear objetos individuales, pondríamos esto:
    # edit "HOST_GESTION"
    #     set subnet 10.0.10.10 255.255.255.255
    # next
    # edit "HOST_PRUEBAS_MEDICAS"
    #     set subnet 10.0.30.10 255.255.255.255
    # next
    # edit "HOST_ELECTRO"
    #     set subnet 10.0.30.20 255.255.255.255
    # next
    # edit "HOST_GAMMA_KNIFE"
    #     set subnet 10.0.30.30 255.255.255.255
    # next
    # edit "CAMARA1"
    #     set subnet 10.0.20.11 255.255.255.255
    # next
    # Así sería por cada host
end

# ——————————————————————————
# Firewall Policy
# ——————————————————————————
# Políticas entre VLANs internas, según segmentación y necesidades de lo que queramos hacer.

config firewall policy
    # VLAN10 (gestión) → VLAN30 (equipos de medicina) 
    edit 10
        set name "GESTION→MEDICINA"
        set srcintf "VLAN10"
        set dstintf "VLAN30"
        set srcaddr "VLAN10_NET"
        set dstaddr "VLAN30_NET"
        set action accept
        set schedule "always"
        set service "ALL"
        set logtraffic all
    next
    # VLAN10 (gestión) → VLAN20 (cámaras)
    edit 11
        set name "GESTION→CAMARAS"
        set srcintf "VLAN10"
        set dstintf "VLAN20"
        set srcaddr "VLAN10_NET"
        set dstaddr "VLAN20_NET"
        set action accept
        set schedule "always"
        set service "ALL"
        set logtraffic all
    next
    # VLAN20 → VLAN30 (denegamos cámaras a medicina)
    edit 12
        set name "CAMARAS→MEDICINA"
        set srcintf "VLAN20"
        set dstintf "VLAN30"
        set srcaddr "VLAN20_NET"
        set dstaddr "VLAN30_NET"
        set action deny
        set schedule "always"
        set service "ALL"
        set logtraffic all
    next
    # VLAN30 → VLAN20  (deny inverso)
    edit 13
        set name "MEDICINA→CAMARAS"
        set srcintf "VLAN30"
        set dstintf "VLAN20"
        set srcaddr "VLAN30_NET"
        set dstaddr "VLAN20_NET"
        set action deny
        set schedule "always"
        set service "ALL"
        set logtraffic all
    next

    # VLAN30 → VLAN10 (permitimos solo gestión desde medicina a gestión)
    edit 14
        set name "MEDICINA→GESTION"
        set srcintf "VLAN30"
        set dstintf "VLAN10"
        set srcaddr "VLAN30_NET"
        set dstaddr "VLAN10_NET"
        set action accept
        set schedule "always"
        set service "SSH" "HTTPS"
        set logtraffic all
    next

    # ——————————————————————————
    # Políticas DMZ ↔ Interno/Internet
    # ——————————————————————————

    # DMZ (WEB) → VLANs internas
    #    (Normalmente deberíamos de bloquear el acceso; en caso de que se quiera permitir algún servicio,
    #     por ejemplo que la web consulte la base de datos interna, se debería de hacer aquí)
    edit 20
        set name "WEB_DMZ→MEDICINA"
        set srcintf "port3"
        set dstintf "VLAN30"
        set srcaddr "DMZ_WEBSERVER"
        set dstaddr "VLAN30_NET"
        set action accept
        set schedule "always"
        set service "MYSQL" "HTTPS"
        set logtraffic all
    next
    # Denegar DMZ → RESTO INTERNOS
    edit 21
        set name "DENY_DMZ→INTERNAS"
        set srcintf "port3"
        set dstintf "VLAN10"
        set srcaddr "DMZ_NET"
        set dstaddr "VLAN10_NET"
        set action deny
        set schedule "always"
        set service "ALL"
        set logtraffic all
    next
    edit 22
        set name "DENY_DMZ→INTERNAS2"
        set srcintf "port3"
        set dstintf "VLAN20"
        set srcaddr "DMZ_NET"
        set dstaddr "VLAN20_NET"
        set action deny
        set schedule "always"
        set service "ALL"
        set logtraffic all
    next

    # VLANs internas → DMZ (solo permitir tráfico necesario)
    edit 23
        set name "MEDICOS→WEB_DMZ"
        set srcintf "VLAN30"
        set dstintf "port3"
        set srcaddr "VLAN30_NET"
        set dstaddr "DMZ_WEBSERVER"
        set action accept
        set schedule "always"
        set service "HTTP" "HTTPS"
        set logtraffic all
    next
    edit 24
        set name "GESTION→WEB_DMZ"
        set srcintf "VLAN10"
        set dstintf "port3"
        set srcaddr "VLAN10_NET"
        set dstaddr "DMZ_WEBSERVER"
        set action accept
        set schedule "always"
        set service "SSH" "HTTPS"
        set logtraffic all
    next

    # VLANs internas → Internet (vía DMZ → Palo Alto)
    edit 30
        set name "INTERNET_FROM_INTERNAS"
        set srcintf "VLAN10"
        set dstintf "port3"
        set srcaddr "VLAN10_NET"
        set dstaddr "all"
        set action accept
        set schedule "always"
        set service "ALL"
        set nat enable
        set logtraffic all
    next
    edit 31
        set name "INTERNET_FROM_CAMARAS"
        set srcintf "VLAN20"
        set dstintf "port3"
        set srcaddr "VLAN20_NET"
        set dstaddr "all"
        set action accept
        set schedule "always"
        set service "ALL"
        set nat enable
        set logtraffic all
    next
    edit 32
        set name "INTERNET_FROM_MEDICINA"
        set srcintf "VLAN30"
        set dstintf "port3"
        set srcaddr "VLAN30_NET"
        set dstaddr "all"
        set action accept
        set schedule "always"
        set service "ALL"
        set nat enable
        set logtraffic all
    next
end

# ——————————————————————————
# Rutas estáticas
# ——————————————————————————
config router static
    # Rutas a subredes internas ya se conocen por el fortigate

    # Ruta default → Palo Alto en DMZ
    edit 0
        set gateway 10.0.200.20
        set device "port3"
    next
end

# ——————————————————————————
# Guardamos cambios
# ——————————————————————————
execute config-save
"""

def configure_firewall():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    print("[+] Conectando al Fortigate...")
    client.connect(hostname, port=port, username=username, password=password)

    remote_shell = client.invoke_shell()
    time.sleep(1)

    print("[+] Enviando configuración...")
    for line in commands.strip().split('\n'):
        remote_shell.send((line + '\n').encode('utf-8'))
        time.sleep(0.25)
        # Se lee el output parcial para no saturar el buffer
        output = remote_shell.recv(5000).decode('utf-8')
        print(output, end='')

    print("\n[+] Configuración finalizada. Cerrando conexión...")
    remote_shell.close()
    client.close()

if __name__ == "__main__":
    configure_firewall()