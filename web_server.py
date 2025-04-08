import json
import os
import sys
import threading
import socket

HOST = ''  # Listen on all available interfaces
PORT = 8733  # Port to listen on

command_line = sys.argv
try:
    CHAT_SERVER_HOST = command_line[1]
except IndexError:
    print("Chat server host not provided, using default.")
    CHAT_SERVER_HOST = "localhost"
CHAT_SERVER_PORT = 8732

web_clients = []
deleted_messages_id = []

base_dir = os.path.join(os.getcwd(), 'files')


def getMethod(http_request):
    return http_request.split()[0]


def getPath(http_request):
    return http_request.split()[1]


def getHeaders(http_request):
    lines = http_request.split('\r\n')
    headers = {}

    for line in lines:
        if ": " in line:
            key, value = line.split(": ", 1)
            headers[key] = value

    return headers


def getBody(http_request, conn):
    header, body = http_request.split('\r\n\r\n', 1)
    headers = getHeaders(http_request)
    content_length = int(headers.get('Content-Length', 0))

    while len(body) < content_length:
        body += conn.recv(1024).decode()

    return body


def send_error(status_code, body):
    response = f'HTTP/1.1 {status_code}\r\n'
    response += 'Content-Type: text/html\r\n'
    response += f'Content-Length: {len(body)}\r\n\r\n'
    response += body
    return response


def isLoggedIn(http_request):
    headers = getHeaders(http_request)
    if 'Cookie' in headers:
        cookies = headers['Cookie'].split('; ')
        for cookie in cookies:
            if cookie.startswith('username='):
                username = cookie.split('=', 1)[1]
                if username in web_clients:
                    return True
    return False


def getUsername(http_request):
    headers = getHeaders(http_request)
    if 'Cookie' in headers:
        cookies = headers['Cookie'].split('; ')
        for cookie in cookies:
            if cookie.startswith('username='):
                return cookie.split('=')[1]


def open_file(file):
    with open(file, 'r') as file:
        body = file.read()
        return body


def handle_client(conn):
    try:
        http_request = conn.recv(1024).decode().strip()
        method = getMethod(http_request)
        path = getPath(http_request)

        if method == 'GET':
            identify = b'GET'
            if path == '/':
                body = open_file("files/index.html")
                response = 'HTTP/1.1 200 OK\r\n'
                response += 'Content-Type: text/html\r\n'
                response += f'Content-Length: {len(body)}\r\n\r\n'
                response += body
                conn.sendall(response.encode())
            elif path == '/api/login':
                if isLoggedIn(http_request):
                    username = getUsername(http_request)
                    body = json.dumps({"user": username})
                    response = 'HTTP/1.1 200 OK\r\n'
                    response += 'Content-Type: application/json\r\n'
                    response += f'Content-Length: {len(body)}\r\n\r\n'
                    response += body
                    conn.sendall(response.encode())
                else:
                    body = open_file("files/index.html")
                    response = send_error("401 Unauthorized", body)
                    conn.sendall(response.encode())

            elif "/api/messages" in path:
                if isLoggedIn(http_request):
                    if "last=" in path:
                        timestamp = path.split('last=')[1].replace("%20", " ")
                    else:
                        timestamp = 'none'

                    try:
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as CHAT_SOCKET:
                            CHAT_SOCKET.connect((CHAT_SERVER_HOST, CHAT_SERVER_PORT))
                            CHAT_SOCKET.sendall(identify + timestamp.encode())

                            messages = b''
                            length_byte = CHAT_SOCKET.recv(4)
                            length = int.from_bytes(length_byte, 'big')

                            while len(messages) < length:
                                piece = CHAT_SOCKET.recv(1024)
                                if not piece:
                                    break
                                messages += piece

                            messages = messages.decode()

                            body = json.dumps({
                                "messages": messages,
                                "deletedMessages": deleted_messages_id
                            })
                            response = 'HTTP/1.1 200 OK\r\n'
                            response += 'Content-Type: application/json\r\n'
                            response += f'Content-Length: {len(body)}\r\n\r\n'
                            response += body
                            conn.sendall(response.encode())
                    except (ConnectionRefusedError, ConnectionResetError) as e:
                        print("Chat server is unavailable")
                        response = send_error("503 Service Unavailable",
                                              json.dumps({"error": "Server is unavailable. Please try again later."}))
                        conn.sendall(response.encode())
                else:
                    response = send_error("401 Unauthorized", "Unauthorized to view this page")
                    conn.sendall(response.encode())
            else:
                fileName = path.lstrip('/')
                file = os.path.join(base_dir, fileName)
                content_types = {
                    '.html': 'text/html',
                    '.css': 'text/css',
                    '.js': 'application/javascript',
                    '.json': 'application/json',
                    '.png': 'image/png',
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.gif': 'image/gif',
                    '.txt': 'text/plain',
                    '.pdf': 'application/pdf'
                }

                file_type = "." + path.split('.')[-1]
                content_type = content_types.get(file_type, 'application/octet-stream')

                if os.path.isfile(file):
                    with open(file, 'rb') as f:
                        body = f.read()

                    response = 'HTTP/1.1 200 OK\r\n'
                    response += f'Content-Type: {content_type}\r\n'
                    response += f'Content-Length: {len(body)}\r\n\r\n'

                    conn.sendall(response.encode())
                    conn.sendall(body)

                else:
                    response = send_error("404 Not Found", "Page not found")
                    conn.sendall(response.encode())

        elif method == 'POST':
            if path == "/api/login":
                body = getBody(http_request, conn)
                identify = b'LOG'
                username = json.loads(body)['username']

                if username in web_clients:
                    body = json.dumps({"message": "already logged in with other client"})
                    response = send_error("409 Conflict", body)
                    conn.sendall(response.encode())
                else:

                    try:
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as CHAT_SOCKET:
                            CHAT_SOCKET.connect((CHAT_SERVER_HOST, CHAT_SERVER_PORT))
                            CHAT_SOCKET.sendall(identify)
                            web_clients.append(username)
                    except (ConnectionRefusedError, ConnectionResetError) as e:
                        print("Chat server is unavailable")
                        response = send_error("503 Service Unavailable",
                                              json.dumps({"error": "Server is unavailable. Please try again later."}))
                        conn.sendall(response.encode())
                    body = json.dumps({"message": "success"})
                    response = 'HTTP/1.1 200 OK\r\n'
                    response += 'Content-Type: application/json\r\n'
                    response += f'Set-Cookie: username={username}; Max-Age=2592000; Path=/; HttpOnly\r\n'
                    response += f'Content-Length: {len(body.encode())}\r\n\r\n'
                    response += body
                    conn.sendall(response.encode())

            elif path == "/api/messages":
                if isLoggedIn(http_request):
                    body = getBody(http_request, conn)
                    message = json.loads(body)['message']
                    username = getUsername(http_request)
                    identify = b'POS'

                    data = json.dumps({"username": username, "message": message})

                    try:
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as CHAT_SOCKET:
                            CHAT_SOCKET.connect((CHAT_SERVER_HOST, CHAT_SERVER_PORT))
                            CHAT_SOCKET.sendall(identify + data.encode())
                    except (ConnectionRefusedError, ConnectionResetError) as e:
                        print("Chat server is unavailable")
                        response = send_error("503 Service Unavailable",
                                              json.dumps(
                                                  {"error": "Server is unavailable. Please try again later."}))
                        conn.sendall(response.encode())

                    body = json.dumps({"message": "success"})
                    response = 'HTTP/1.1 200 OK\r\n'
                    response += 'Content-Type: application/json\r\n'
                    response += f'Content-Length: {len(body.encode())}\r\n\r\n'
                    response += body
                    conn.sendall(response.encode())
                else:
                    response = send_error("401 Unauthorized", "Unauthorized to view this page")
                    conn.sendall(response.encode())
            else:
                response = send_error("404 Not Found", "Page not found")
                conn.sendall(response.encode())
        elif method == 'DELETE':
            identify = b'DEL'
            if path == "/api/login":
                if isLoggedIn(http_request):
                    username = getUsername(http_request)

                    body = json.dumps({"message": "Log Out success"})
                    web_clients.remove(username)
                    response = 'HTTP/1.1 200 OK\r\n'
                    response += 'Content-Type: application/json\r\n'
                    response += 'Set-Cookie: username=; Max-Age=0; Path=/; HttpOnly\r\n'
                    response += f'Content-Length: {len(body.encode())}\r\n\r\n'
                    response += body
                    conn.sendall(response.encode())
                else:
                    response = send_error("401 Unauthorized", "Unauthorized to view this page")
                    conn.sendall(response.encode())
            elif "/api/messages" in path:
                if isLoggedIn(http_request):
                    messageID = path.split('/')[-1]
                    try:
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as CHAT_SOCKET:
                            CHAT_SOCKET.connect((CHAT_SERVER_HOST, CHAT_SERVER_PORT))
                            CHAT_SOCKET.sendall(identify + messageID.encode())

                            messages = b''
                            length_byte = CHAT_SOCKET.recv(4)
                            length = int.from_bytes(length_byte, 'big')

                            while len(messages) < length:
                                piece = CHAT_SOCKET.recv(1024)
                                if not piece:
                                    break
                                messages += piece

                            messages = messages.decode()

                            body = json.dumps({"messages": messages})
                            deleted_messages_id.append(messageID)
                            response = 'HTTP/1.1 200 OK\r\n'
                            response += 'Content-Type: application/json\r\n'
                            response += f'Content-Length: {len(body)}\r\n\r\n'
                            response += body
                            conn.sendall(response.encode())
                    except (ConnectionRefusedError, ConnectionResetError) as e:
                        print("Chat server is unavailable")
                        response = send_error("503 Service Unavailable",
                                              json.dumps(
                                                  {"error": "Server is unavailable. Please try again later."}))
                        conn.sendall(response.encode())
                else:
                    response = send_error("401 Unauthorized", "Unauthorized to view this page")
                    conn.sendall(response.encode())
            else:
                response = send_error("404 Not Found", "Page not found")
                conn.sendall(response.encode())


    finally:
        conn.close()


def start_server():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as web_socket:
            web_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            web_socket.bind((HOST, PORT))
            web_socket.listen()
            print(f"Web server is listening on {socket.gethostname()} interface on port {PORT}")

            while True:
                try:
                    conn, addr = web_socket.accept()
                    print(f"Connection from {addr}")
                    threading.Thread(target=handle_client, args=(conn,)).start()
                except Exception as e:
                    print(f"Error accepting connection: {e}")
    except KeyboardInterrupt:
        print("Why did you kill me")
        sys.exit(0)
    except Exception as e:
        print("An error occurred:")
        print(e)


if __name__ == "__main__":
    start_server()
