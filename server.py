import json
import select
import socket
import sqlite3
import sys

HOST = ''
PORT = 8731
MESSAGE_COUNT = 80  # number of maximum messages we want to display to client

WEB_SERVER_HOST = 'localhost'
WEB_SERVER_PORT = 8732


def create_message_table(sqliteconnect):
    with sqliteconnect:
        table = ("create table if not exists messages("
                 "messageID integer primary key autoincrement,"
                 "username text not null,"
                 "message text not null,"
                 "sql_time datetime default current_timestamp not null"
                 ");"
                 )
        sqliteconnect.execute(table)


def create_user_table(sqliteconnect):
    with sqliteconnect:
        table = ("create table if not exists users("
                 "userID integer primary key autoincrement,"
                 "username text unique not null,"
                 "time_disconnect datetime default current_timestamp not null"
                 ");"
                 )
        sqliteconnect.execute(table)


def create_web_user_table(sqliteconnect):
    with sqliteconnect:
        table = ("create table if not exists webclients("
                 "webclientID integer primary key autoincrement,"
                 "username text unique not null,"
                 "time_disconnect datetime default current_timestamp not null"
                 ");"
                 )
        sqliteconnect.execute(table)


def store_messages(sqliteconnect, username, message):
    with sqliteconnect:
        sql = "insert into messages (username, message,sql_time) values (?,?, current_timestamp)"
        values = (username, message)
        sqliteconnect.execute(sql, values)


def table_size(sqliteconnect):
    cursor = sqliteconnect.cursor()
    cursor.execute("select count(*) from messages;")
    count = cursor.fetchone()[0]
    return count


# calculates the offset to get the recent 80 messages in the table
def cal_offset(sqliteconnect):
    size = table_size(sqliteconnect)
    return max(0, size - MESSAGE_COUNT)


def retrieve_messages_after_time(timestamp, sqliteconnect):
    offset = cal_offset(sqliteconnect)
    cursor = sqliteconnect.cursor()

    try:
        sql = "SELECT * FROM messages WHERE sql_time > ?  ORDER BY messageID LIMIT ? OFFSET ?"
        values = (timestamp, MESSAGE_COUNT, offset)
        cursor.execute(sql, values)

        messages = cursor.fetchall()
        return messages
    except Exception as e:
        print("An error occurred:")
        print(e)
        return []
    finally:
        cursor.close()


def retrieve_messages(sqliteconnect, username):
    offset = cal_offset(sqliteconnect)
    cursor = sqliteconnect.cursor()

    try:
        # get the time the user left the serer
        sql = "select time_disconnect from users where username = ?"
        values = (username,)
        cursor.execute(sql, values)
        time_disconnected = cursor.fetchone()

        if time_disconnected is None:
            # if the user is a new user, send them all messages
            sql = "select * from messages order by messageID limit ? offset ?"
            values = (MESSAGE_COUNT, offset)
            cursor.execute(sql, values)
        else:
            # if the user isn't new, send messages after the time they disconnected
            time_disconnected = time_disconnected[0]
            sql = "select * from messages where sql_time > ? order by messageID limit ? offset ?"
            values = (time_disconnected, MESSAGE_COUNT, offset)
            cursor.execute(sql, values)

        messages = cursor.fetchall()
        return messages
    except Exception as e:
        print("An error occurred:")
        print(e)
    finally:
        cursor.close()


def retrieve_messages_web(sqliteconnect):
    cursor = sqliteconnect.cursor()

    try:
        sql = "SELECT * FROM messages ORDER BY messageID LIMIT ?"
        values = (MESSAGE_COUNT,)
        cursor.execute(sql, values)

        messages = cursor.fetchall()
        return messages
    except Exception as e:
        print("An error occurred:")
        print(e)
        return []
    finally:
        cursor.close()


def is_table_empty(sqliteconnect):
    return table_size(sqliteconnect) == 0


def store_user_disconnected(sqliteconnect, username):
    with sqliteconnect:
        sql = ("insert into users (username , time_disconnect) values (?, current_timestamp) "
               "on conflict(username) do update set time_disconnect = current_timestamp"
               )
        values = (username,)
        sqliteconnect.execute(sql, values)


def delete_message(sqliteconnect, messageID):
    cursor = sqliteconnect.cursor()
    try:
        sql = "DELETE FROM messages WHERE messageID = ?"
        values = (messageID,)
        cursor.execute(sql, values)

        messages = cursor.fetchall()
        return messages
    except Exception as e:
        print("An error occurred:")
        print(e)
        return []
    finally:
        cursor.close()


def handle_terminal_client(client, sqliteconnect, terminal_clients):
    data = b''

    username = ''
    for user, conn in terminal_clients.items():
        if conn == client:
            username = user
            break

    # To handle telnet connection
    initial = client.recv(6, socket.MSG_PEEK)
    if not initial:
        print("Connection closed")

    if len(initial) >= 2 and initial[:2] == b'ME':
        # checks if it's the client created by me which has a
        # placeholder and a length of 4 bytes
        initial = client.recv(6)
        length_byte = initial[2:6]
        length = int.from_bytes(length_byte, 'big')

        while len(data) < length:
            piece = client.recv(1024)
            if not piece:
                break
            data += piece
    else:
        data = client.recv(1024)

    if data:
        message = data.decode().strip()
        try:
            split_message = message.split("-", 1)
            message_sql = split_message[1].strip()
            username = split_message[0].strip()

            print(f"heard from client:\n"
                  f"{message}\n")

            store_messages(sqliteconnect, username, message_sql)

            # send the message to all the clients
            for c in terminal_clients.values():
                try:
                    c.sendall(data)
                except BrokenPipeError:
                    print(f"Couldn't send message to {username}")


        except Exception as e:
            error_message = ("Could not understand.\nPlease follow the format: "
                             "'username - message'.\n")
            print("Could not understand")
            terminal_clients[username].sendall(error_message.encode())

    else:
        # if the user typed quit or disconnects
        print(f"{username} has disconnected\n")
        store_user_disconnected(sqliteconnect, username)
        terminal_clients[username].close()
        del terminal_clients[username]


def handle_web_client(conn, sqliteconnect, terminal_clients, telnet_clients, web_clients):
    method = conn.recv(3)
    if method == b'GET':
        data = conn.recv(1024)

        if not data:
            return

        timestamp = data.decode().strip()
        if timestamp == 'none':
            messages = retrieve_messages_web(sqliteconnect)
        else:
            messages = retrieve_messages_after_time(timestamp, sqliteconnect)

        message_list = [
            {
                "messageID": message[0],
                "username": message[1],
                "message": message[2],
                "timestamp": message[3]
            }
            for message in messages
        ]

        response_body = json.dumps(message_list)
        length = len(response_body).to_bytes(4, 'big')  # lets us know the size of the message
        conn.sendall(length + response_body.encode())

    elif method == b'POS':
        data = conn.recv(1024)
        if not data:
            return
        data = data.decode().strip()

        try:
            json_data = json.loads(data)

            username = json_data.get("username")
            message = json_data.get("message")
            store_messages(sqliteconnect, username, message)
            print(f"heard from client:\n"
                  f"{username}-{message}\n")

            # send the message to all the terminal clients
            for c in terminal_clients.values():
                try:
                    c.sendall(f"{username} - {message}".encode())
                except BrokenPipeError:
                    print(f"Couldn't send message to {username}")
            for c in telnet_clients:
                try:
                    c.sendall(f"{username} - {message}".encode())
                except BrokenPipeError:
                    print(f"Couldn't send message to {username}")

        except json.JSONDecodeError:
            return
    elif method == b'DEL':
        data = conn.recv(1024)
        if not data:
            return

        messageID = data.decode().strip()
        messages = delete_message(sqliteconnect, messageID)

        message_list = [
            {
                "messageID": message[0],
                "username": message[1],
                "message": message[2],
                "timestamp": message[3]
            }
            for message in messages
        ]

        response_body = json.dumps(message_list)
        length = len(response_body).to_bytes(4, 'big')  # lets us know the size of the message
        conn.sendall(length + response_body.encode())


def start_server():
    # create a server socket using TCP socket
    sqliteconnect = sqlite3.connect('gfg.db')
    create_message_table(sqliteconnect)
    create_user_table(sqliteconnect)
    create_web_user_table(sqliteconnect)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        print(f"listening on {socket.gethostname()} interface on port {PORT}")

        web_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        web_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        web_socket.bind((HOST, WEB_SERVER_PORT))
        web_socket.listen()
        print(f"listening to web server {socket.gethostname()} interface on port {WEB_SERVER_PORT}")

        terminal_clients = {}
        web_clients = []
        telnet_clients = []

        while True:
            try:
                inputs = list(terminal_clients.values()) + [s] + [web_socket] + web_clients + telnet_clients

                readable, writeable, exceptional = select.select(inputs, [], inputs)

                for client in readable:
                    if client is s:
                        # New terminal client connection
                        conn, addr = s.accept()
                        print(f"New terminal client connected from {addr}")

                        conn.settimeout(1)
                        try:
                            initial = conn.recv(2, socket.MSG_PEEK)
                        except socket.timeout:
                            # No data received within the timeout period, likely a Telnet client
                            print("Telnet client detected by timeout")
                            telnet_clients.append(conn)
                            conn.settimeout(None)
                            conn.sendall("Connected to server via Telnet\n".encode())
                            continue
                        finally:
                            conn.settimeout(None)

                        if not initial:
                            print("Connection closed")
                            conn.close()
                            continue

                        if len(initial) >= 2 and initial[:2] == b'ME':
                            conn.recv(2)
                            username = conn.recv(1024).decode().strip()

                            if username in terminal_clients.keys():
                                # if a client with that same username is already connected on the server
                                print(f"{username} already here. Disconnecting the other client\n")
                                other_client = terminal_clients[username]
                                other_client.sendall("Logging you out due to other connection".encode())
                                store_user_disconnected(sqliteconnect, username)
                                other_client.close()
                                del terminal_clients[username]

                            terminal_clients[username] = conn
                            print(f"Terminal client {username} connected")

                            if not is_table_empty(sqliteconnect):
                                # retrieve the old messages and send to the new client
                                old_messages = retrieve_messages(sqliteconnect, username)
                                if not old_messages:
                                    terminal_clients[username].sendall(f"----------No new messages-----------".encode())
                                for messageID, username, message, sql_time in old_messages:
                                    conn.sendall(f"{username} - {message}\n".encode())
                    elif client is web_socket:
                        conn, addr = web_socket.accept()
                        print("Web socket connected")

                        sent_username = conn.recv(3, socket.MSG_PEEK)

                        # if its the web client first time connecting
                        if sent_username == b'LOG':
                            conn.recv(3)

                            print(f"Web client connected")
                            web_clients.append(conn)
                        else:
                            handle_web_client(conn, sqliteconnect, terminal_clients, telnet_clients, web_clients)

                    elif client in web_clients:
                        handle_web_client(client, sqliteconnect, terminal_clients, telnet_clients, web_clients)
                    elif client in terminal_clients.values():
                        handle_terminal_client(client, sqliteconnect, terminal_clients)
            except KeyboardInterrupt:
                print("Why did you kill me")
                for user, conn in terminal_clients.items():
                    store_user_disconnected(sqliteconnect, user)
                    conn.close()
                for user, conn in web_clients:
                    conn.close()
                sys.exit(0)

            except Exception as e:
                print("An error occurred:")
                print(e)


if __name__ == "__main__":
    start_server()
