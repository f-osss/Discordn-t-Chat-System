## Multi-threaded API web server
### A multi-threaded web server that serves dynamic content. Specifically a website that uses Javascript to populate and post to “Discordn’t”.
### How to start the chat server

To start the chat server, you run the following command into the terminal (Linux, macOS, or WSL recommended):

```
python3 server.py
```

### How to start the web server

To start the web server, you need to provide the hostname of the machine where the chat server is running. For example,
if the chat server is running on falcon.cs.umanitoba.ca, you would run:

```
python3 web_server.py falcon.cs.umanitoba.ca
```

### How to start the web client

To access the web client, navigate to your browser and connect to the web server by entering the hostname and port (
8733). It's need to connect to the web
server using port 8733:
For example, if running on falcon:

```
http://falcon.cs.umanitoba.ca:8733/
```

### Notes about web client

Multiple webclients cannot be logged in with the same username. A username can only be logged in from one web client at
a time. If a user attempts to log in with a username that is already in use, an error message will display:
```Username already in use by another client, choose a different username.```

If the chat server is unavailable while the web_client is active, the web_client is shown an error :
```Server is unavailable. Please try again later.```

When testing my web client on aviary, Chrome said ```This site can’t be reached
The connection was reset.``` . However, running it in an incognito window in chrome worked fine. It also worked fine while
running it on Microsoft Edge.

### How to start the terminal client

To start the client, you need to provide a username, host and port via to the command line. It's currently running on
port 8731:

```
python3 client.py "username" "hostname" 8731
```

### Terminal Client Quitting

The client needs to send **quit** as a message to disconnect

### Bonus

When a user sends a message in the web browser, it is displayed on the right side of the screen
with a delete button. Clicking the delete button removes the message for all connected web clients.

### System test in C

A MakeFile has been provided to compile the C screen scraper client. To compile, type
```make``` into the terminal

## Running the system test

To run the scraper client, you'll need to know the host and port where the web server is currently running. The command
format is as follows:

```
./scraper_client [host] [port] [username] [message]

[host]: The hostname or IP address of the web server (e.g., falcon.cs.umanitoba.ca).
[port]: The port where the web server is listening for incoming connections (e.g., 8733).
[username]: A unique username for the client (ensure this is not already in use by another web client).
[message]: The message you want to send through the system test.
```

The username used for this test can not be the same as an active web client username, as the system only allows unique
usernames.

### Notes about System test:

When running on Aviary, if the machine the scraper test is running on is not the same as the web server, it was unable
to form a connection.

### Additional information

Port Information:

The chat_server uses two ports:
Port ```8731``` for communication with terminal clients.
Port ```8732``` for communication with the web_server.
The web_server uses port ```8733``` to communicate with the web client (accessed via the browser).

## Note: This project was developed and tested on the Aviary server at the University of Manitoba. When running locally or on another server, make sure the correct hostname and ports are used.


