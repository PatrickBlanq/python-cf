import os
import re
import json
import time
import base64
import shutil
import asyncio
import requests
import platform
import subprocess
import threading
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

#https://share.streamlit.io/
# Environment variables
UPLOAD_URL = os.environ.get('UPLOAD_URL', '')          # 节点或订阅上传地址,只填写这个地址将上传节点,同时填写PROJECT_URL将上传订阅，例如：https://merge.serv00.net
PROJECT_URL = os.environ.get('PROJECT_URL', '')        # 项目url,需要自动保活或自动上传订阅需要填写,例如：https://www.google.com,
AUTO_ACCESS = os.environ.get('AUTO_ACCESS', 'false').lower() == 'true'  # false关闭自动保活, true开启自动保活，默认关闭
FILE_PATH = os.environ.get('FILE_PATH', './.cache')    # 运行路径,sub.txt保存路径
SUB_PATH = os.environ.get('SUB_PATH', 'sub')           # 订阅token,默认sub，例如：https://www.google.com/sub
UUID = os.environ.get('UUID', '792c9cd6-9ece-4ebc-ff02-86eaf8bf7e73')  # UUID,如使用哪吒v1,在不同的平台部署需要修改,否则会覆盖

#NEZHA_SERVER = os.environ.get('NEZHA_SERVER', '')      # 哪吒面板域名或ip, v1格式: nezha.xxx.com:8008, v0格式: nezha.xxx.com
#NEZHA_PORT = os.environ.get('NEZHA_PORT', '')          # v1哪吒请留空, v0哪吒的agent通信端口,自动匹配tls
#NEZHA_KEY = os.environ.get('NEZHA_KEY', '')            # v1哪吒的NZ_CLIENT_SECRET或v0哪吒agent密钥

ARGO_DOMAIN = os.environ.get('ARGO_DOMAIN', 'ms.ai7g.eu.org')        # Argo固定隧道域名,留空即使用临时隧道
ARGO_AUTH = os.environ.get('ARGO_AUTH', 'eyJhIjoiODdiZmI2YjUxMjVmM2UxMDExYTQ5YTY1MWYyMTUwMTkiLCJ0IjoiMjYzNzkyZjYtMzFiMC00NzU2LTg3OTktNzA1MGM2MzdhMWZkIiwicyI6Ill6Y3hOV05tTjJJdE1tSXpOeTAwTUdWaUxUZ3dPVEV0T0dSaU5HTmxaVFJtTW1WaSJ9')            # Argo固定隧道ms.ai7g.eu.org

#ARGO_AUTH = os.environ.get('ARGO_AUTH', 'eyJhIjoiODdiZmI2YjUxMjVmM2UxMDExYTQ5YTY1MWYyMTUwMTkiLCJ0IjoiMDgyNDhmNWYtZWY5MC00MmVlLWI5NjctY2JiNjY2ZDBlMzYyIiwicyI6Ik9UWTVNbUl4WTJVdFpXRTVaaTAwTURNeUxXRmhOakV0WVRabU5qaGlPVFEzWlRSaSJ9')            # Argo固定t31隧道密钥,留空即使用临时隧道

ARGO_PORT = int(os.environ.get('ARGO_PORT', '2777'))   # Argo端口,使用固定隧道token需在cloudflare后台设置端口和这里一致
CFIP = os.environ.get('CFIP', 'm2.u.cloudns.be')       # 优选ip或优选域名

CFPORT = int(os.environ.get('CFPORT', '443'))          # 优选ip或优选域名对应端口
NAME = os.environ.get('NAME', 'Vls')                   # 节点名称
CHAT_ID = os.environ.get('CHAT_ID', '')                # Telegram chat_id,推送节点到tg,两个变量同时填写才会推送
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')            # Telegram bot_token
PORT = int(os.environ.get('SERVER_PORT') or os.environ.get('PORT') or 8080) # 订阅端口，如无法订阅，请手动修改为分配的端口

# Create running folder
def create_directory():
    print('\033c', end='')
    if not os.path.exists(FILE_PATH):
        os.makedirs(FILE_PATH)
        print(f"{FILE_PATH} is created")
    else:
        print(f"{FILE_PATH} already exists")

# Global variables
npm_path = os.path.join(FILE_PATH, 'npm')
php_path = os.path.join(FILE_PATH, 'php')
web_path = os.path.join(FILE_PATH, 'web')
bot_path = os.path.join(FILE_PATH, 'bot')
sub_path = os.path.join(FILE_PATH, 'sub.txt')
list_path = os.path.join(FILE_PATH, 'list.txt')
boot_log_path = os.path.join(FILE_PATH, 'boot.log')
config_path = os.path.join(FILE_PATH, 'config.json')

# Delete nodes
def delete_nodes():
    try:
        if not UPLOAD_URL:
            return

        if not os.path.exists(sub_path):
            return

        try:
            with open(sub_path, 'r') as file:
                file_content = file.read()
        except:
            return None

        decoded = base64.b64decode(file_content).decode('utf-8')
        nodes = [line for line in decoded.split('\n') if any(protocol in line for protocol in ['vless://', 'vmess://', 'trojan://', 'hysteria2://', 'tuic://'])]

        if not nodes:
            return

        try:
            requests.post(f"{UPLOAD_URL}/api/delete-nodes", 
                          data=json.dumps({"nodes": nodes}),
                          headers={"Content-Type": "application/json"})
        except:
            return None
    except Exception as e:
        print(f"Error in delete_nodes: {e}")
        return None

# Clean up old files
def cleanup_old_files():
    paths_to_delete = ['web', 'bot', 'npm', 'php', 'boot.log', 'list.txt']
    for file in paths_to_delete:
        file_path = os.path.join(FILE_PATH, file)
        try:
            if os.path.exists(file_path):
                if os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                else:
                    os.remove(file_path)
        except Exception as e:
            print(f"Error removing {file_path}: {e}")

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'Hello World')
            
        elif self.path == f'/{SUB_PATH}':
            try:
                with open(sub_path, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(content)
            except:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass
    
# Determine system architecture
def get_system_architecture():
    architecture = platform.machine().lower()
    if 'arm' in architecture or 'aarch64' in architecture:
        return 'arm'
    else:
        return 'amd'

# Download file based on architecture
def download_file(file_name, file_url):
    file_path = os.path.join(FILE_PATH, file_name)
    try:
        response = requests.get(file_url, stream=True)
        response.raise_for_status()
        
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"Download {file_name} successfully")
        return True
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        print(f"Download {file_name} failed: {e}")
        return False

# Get files for architecture
def get_files_for_architecture(architecture):
    if architecture == 'arm':
        base_files = [
            {"fileName": "web", "fileUrl": "https://arm64.ssss.nyc.mn/web"},
            {"fileName": "bot", "fileUrl": "https://arm64.ssss.nyc.mn/2go"}
        ]
    else:
        base_files = [
            {"fileName": "web", "fileUrl": "https://amd64.ssss.nyc.mn/web"},
            {"fileName": "bot", "fileUrl": "https://amd64.ssss.nyc.mn/2go"}
        ]
 

    return base_files

# Authorize files with execute permission
def authorize_files(file_paths):
    for relative_file_path in file_paths:
        absolute_file_path = os.path.join(FILE_PATH, relative_file_path)
        if os.path.exists(absolute_file_path):
            try:
                os.chmod(absolute_file_path, 0o775)
                print(f"Empowerment success for {absolute_file_path}: 775")
            except Exception as e:
                print(f"Empowerment failed for {absolute_file_path}: {e}")

# Configure Argo tunnel
def argo_type():
    if not ARGO_AUTH or not ARGO_DOMAIN:
        print("ARGO_DOMAIN or ARGO_AUTH variable is empty, use quick tunnels")
        return

    if "TunnelSecret" in ARGO_AUTH:
        with open(os.path.join(FILE_PATH, 'tunnel.json'), 'w') as f:
            f.write(ARGO_AUTH)
        
        tunnel_id = ARGO_AUTH.split('"')[11]
        tunnel_yml = f"""
tunnel: {tunnel_id}
credentials-file: {os.path.join(FILE_PATH, 'tunnel.json')}
protocol: http2

ingress:
  - hostname: {ARGO_DOMAIN}
    service: http://localhost:{ARGO_PORT}
    originRequest:
      noTLSVerify: true
  - service: http_status:404
"""
        with open(os.path.join(FILE_PATH, 'tunnel.yml'), 'w') as f:
            f.write(tunnel_yml)
    else:
        print("Use token connect to tunnel,please set the {ARGO_PORT} in cloudflare")

# Execute shell command and return output
def exec_cmd(command):
    try:
        process = subprocess.Popen(
            command, 
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()
        return stdout + stderr
    except Exception as e:
        print(f"Error executing command: {e}")
        return str(e)

# Download and run necessary files
async def download_files_and_run():
    global private_key, public_key
    
    architecture = get_system_architecture()
    files_to_download = get_files_for_architecture(architecture)
    
    if not files_to_download:
        print("Can't find a file for the current architecture")
        return
    
    # Download all files
    download_success = True
    for file_info in files_to_download:
        if not download_file(file_info["fileName"], file_info["fileUrl"]):
            download_success = False
    
    if not download_success:
        print("Error downloading files")
        return
    
    # Authorize files
    files_to_authorize = ['npm', 'web', 'bot']  
    authorize_files(files_to_authorize)
    


 
    # Generate configuration file
    import json

    config_dict = {
        "inbounds": [
            {
                "listen": "127.0.0.1",
                "port": 2777,
                "protocol": "vmess",
                "settings": {
                    "clients": [
                        {"id": "792c9cd6-9ece-4ebc-ff02-86eaf8bf7e73"}
                    ]
                },
                "streamSettings": {
                    "network": "ws",
                    "wsSettings": {
                        "path": "/792c9cd6-9ece-4ebc-ff02-86eaf8bf7e73"
                    }
                }
            }
        ],
        "outbounds": [
            {
                "protocol": "freedom"
            }
        ]
    }

    # 一行 JSON
    config = json.dumps(config_dict, separators=(',', ':'))

    # 写入文件（正确）
    with open(os.path.join(FILE_PATH, 'config.json'), 'w', encoding='utf-8') as f:
        f.write(config)

    print("config.json saved.")

    # Run nezha


    # Run sbX
    command = f"nohup {os.path.join(FILE_PATH, 'web')} -c {os.path.join(FILE_PATH, 'config.json')} >/dev/null 2>&1 &"
    try:
        exec_cmd(command)
        print('web is running')
        time.sleep(1)
    except Exception as e:
        print(f"web running error: {e}")
    
    # Run cloudflared
    if os.path.exists(os.path.join(FILE_PATH, 'bot')):
        if re.match(r'^[A-Z0-9a-z=]{120,250}$', ARGO_AUTH):
            args = f"tunnel --edge-ip-version auto --no-autoupdate --protocol http2 run --token {ARGO_AUTH}"
        elif "TunnelSecret" in ARGO_AUTH:
            args = f"tunnel --edge-ip-version auto --config {os.path.join(FILE_PATH, 'tunnel.yml')} run"
        else:
            args = f"tunnel --edge-ip-version auto --no-autoupdate --protocol http2 --logfile {os.path.join(FILE_PATH, 'boot.log')} --loglevel info --url http://localhost:{ARGO_PORT}"
        
        try:
            #log_file = os.path.join(FILE_PATH, "cloudflared.log")
            #查看日志
            #exec_cmd(f"nohup {os.path.join(FILE_PATH, 'bot')} {args} > {log_file} 2>&1 &")
            exec_cmd(f"nohup {os.path.join(FILE_PATH, 'bot')} {args} >/dev/null 2>&1 &")
            print("bot is running, log saved to:", log_file)

            time.sleep(2)
        except Exception as e:
            print(f"Error executing command: {e}")
    
    time.sleep(5)
    
    # Extract domains and generate sub.txt
    await extract_domains()

# Extract domains from cloudflared logs
async def extract_domains():
    argo_domain = None

    if ARGO_AUTH and ARGO_DOMAIN:
        argo_domain = ARGO_DOMAIN
        print(f'ARGO_DOMAIN: {argo_domain}')
        #await generate_links(argo_domain)
    else:
        try:
            with open(boot_log_path, 'r') as f:
                file_content = f.read()
            
            lines = file_content.split('\n')
            argo_domains = []
            
            for line in lines:
                domain_match = re.search(r'https?://([^ ]*trycloudflare\.com)/?', line)
                if domain_match:
                    domain = domain_match.group(1)
                    argo_domains.append(domain)
            
            if argo_domains:
                argo_domain = argo_domains[0]
                print(f'ArgoDomain: {argo_domain}')
                #await generate_links(argo_domain)
            else:
                print('ArgoDomain not found, re-running bot to obtain ArgoDomain')
                # Remove boot.log and restart bot
                if os.path.exists(boot_log_path):
                    os.remove(boot_log_path)
                
                try:
                    exec_cmd('pkill -f "[b]ot" > /dev/null 2>&1')
                except:
                    pass
                
                time.sleep(1)
                args = f'tunnel --edge-ip-version auto --no-autoupdate --protocol http2 --logfile {FILE_PATH}/boot.log --loglevel info --url http://localhost:{ARGO_PORT}'
                exec_cmd(f'nohup {os.path.join(FILE_PATH, "bot")} {args} >/dev/null 2>&1 &')
                print('bot is running.')
                time.sleep(6)  # Wait 6 seconds
                await extract_domains()  # Try again
        except Exception as e:
            print(f'Error reading boot.log: {e}')

# Clean up files after 90 seconds
def clean_files():
    def _cleanup():
        time.sleep(90)  # Wait 90 seconds
        files_to_delete = [boot_log_path, config_path, list_path, web_path, bot_path, php_path, npm_path]
        for file in files_to_delete:
            try:
                if os.path.exists(file):
                    if os.path.isdir(file):
                        shutil.rmtree(file)
                    else:
                        os.remove(file)
            except:
                pass
        
        print('\033c', end='')
        print('App is running')
        print('Thank you for using this script, enjoy!')
    
    threading.Thread(target=_cleanup, daemon=True).start()
    
# Main function to start the server
async def start_server():
    #delete_nodes()
    cleanup_old_files()
    #create_directory()
    argo_type()
    await download_files_and_run()
    #add_visit_task()
    
    server_thread = Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()   
    
    clean_files()
    
def run_server():
    server = HTTPServer(('0.0.0.0', PORT), RequestHandler)
    print(f"Server is running on port {PORT}")
    print(f"Running done！")
    print(f"\nLogs will be delete in 90 seconds")
    server.serve_forever()

def run_async():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_server()) 
    
    while True:
        time.sleep(3600)
        
if __name__ == "__main__":
    run_async()
