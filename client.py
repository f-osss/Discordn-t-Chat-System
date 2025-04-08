import socket
import select
import sys
import termios

command_line = sys.argv

username = command_line[1]
HOST = command_line[2]
PORT = int(command_line[3])


def clear_terminal():
    sys.stdout.write(
        "\033[2J\033[H\033[3J")  # clears the terminal, moves the cursor to teh top left and prevent scroll back
    sys.stdout.flush()


def start_client():
    fd = sys.stdin.fileno()
    settings = termios.tcgetattr(fd)

    try:
        terminal_settings = termios.tcgetattr(fd)
        terminal_settings[3] = terminal_settings[3] & ~termios.ICANON
        terminal_settings[3] = terminal_settings[3] & ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, terminal_settings)

        buffer = ""  # buffer to store the clients input
        messages = []  # list of all messages sent gotten from the server
        identifier = b'ME'

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect((HOST, PORT))
                s.sendall(identifier + username.encode())

                print(f"Connected to the server as {username}. Type 'quit' to disconnect.")

                while True:
                    readable, writable, exceptional = select.select([s, sys.stdin], [], [s, sys.stdin])

                    # if an action happens either from the user or the server
                    for action in readable:
                        if action is s:
                            # if the action is from the server
                            data = s.recv(1024).decode()
                            if data:
                                messages.append(data)
                                clear_terminal()
                                for message in messages:
                                    print(f"{message}")
                                print(f">>{buffer}", end="", flush=True)
                            else:
                                print("Server has been disconnected")
                                s.close()
                                sys.exit()
                        else:
                            # if the action is from the user, meaning they're sending a message
                            client_message = sys.stdin.read(1)
                            if client_message == '\n':
                                if buffer == 'quit':
                                    print("\nDisconnected")
                                    s.close()
                                    sys.exit()
                                elif buffer != '':
                                    message = f"{username} - {buffer}".encode()
                                    length = len(message).to_bytes(4, 'big')  # lets us know the size of the message
                                    s.sendall(identifier + length + message)
                                    buffer = ""
                                    print(end="\r", flush=True)

                            # if the user pressed backspace
                            elif client_message in ('\x08', '\x7f'):
                                if buffer:
                                    buffer = buffer[:-1]
                                    print(f"\r{' ' * (len(buffer) + 3)}", end="")  # clear the line
                                    print(f"\r>>{buffer}", end="", flush=True)
                            else:
                                buffer += client_message
                                print(f"{client_message}", end="", flush=True)

            except Exception as e:
                print("Server is not connected, Goodbye")

    finally:
        termios.tcsetattr(fd, termios.TCSANOW, settings)


if __name__ == "__main__":
    start_client()
