#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <assert.h>
#include <stdlib.h>

#define BUFFER_SIZE 1024
#define MAX_BUFFER_SIZE (BUFFER_SIZE * 5)

int start_socket(const char *host, int port) {
    int socket_desc;
    struct sockaddr_in server_addr;

    // Create socket:
    socket_desc = socket(AF_INET, SOCK_STREAM, 0);
    if (socket_desc < 0) {
        printf("Unable to create socket\n");
        return -1;
    }

    // Set port and host the same as server-side:
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(port);
    inet_pton(AF_INET, host, &server_addr.sin_addr);

    // Send connection request to server:
    if (connect(socket_desc, (struct sockaddr*)&server_addr, sizeof(server_addr)) < 0) {
        printf("Unable to connect\n");
        close(socket_desc);
        return -1;
    }

    return socket_desc;
}

int check_message_exists(const char *json_response, const char *message) {
    const char *messages_field = strstr(json_response, "\"messages\": \"");
    if (!messages_field) {
        return 0;
    }

    messages_field += strlen("\"messages\": \"");

    char search[256];
    snprintf(search, sizeof(search), "\\\"message\\\": \\\"%s\\\"", message);

    if (strstr(messages_field, search)) {
        return 1;
    } else {
        return 0;
    }
}


void run_test(const char *host, int port, const char *username, const char *message) {
    char login_request[BUFFER_SIZE];
    char fetch_request[BUFFER_SIZE];
    char post_request[BUFFER_SIZE];
    char response[MAX_BUFFER_SIZE] = {0};
    int size;
    int socket;


//    login the user
    printf("Starting test: logging in user (%s)\n", username);
    socket= start_socket(host, port);
    if (socket < 0) {
        return;
    }
    snprintf(login_request, sizeof(login_request),
             "POST /api/login HTTP/1.1\r\nContent-Type: application/json\r\nContent-Length: %zu\r\n\r\n{\"username\":\"%s\"}",
             strlen(username) + 13, username);

    if (send(socket, login_request, strlen(login_request), 0) < 0) {
        printf("Unable to send request\n");
        return;
    }

    if ((size = recv(socket, response, sizeof(response), 0)) <= 0) {
        printf("Error while receiving server's response to login\n");
        close(socket);
        return;
    }
    response[size] = '\0';
    close(socket);

    if(strstr(response, "already logged in with other client")){
        printf("This client is already logged in, pls try again with another username\n");
        return;
    }

    // Fetch the messages (via /api/messages) once to check if the message is not there.
    printf("\nChecking initial message presence on server\n");
    snprintf(fetch_request, sizeof(fetch_request),
             "GET /api/messages HTTP/1.1\r\n"
             "Cookie: username=%s\r\n\r\n",
             username);
    socket= start_socket(host, port);
    if (send(socket, fetch_request, strlen(fetch_request), 0) < 0) {
        printf("Unable to send request\n");
        close(socket);
        return;
    }

    if ((size = recv(socket, response, sizeof(response), 0)) <= 0) {
        printf("Error while receiving server's mssages\n");
        close(socket);
        return;
    }
    response[size] = '\0';
    close(socket);

    if (check_message_exists(response, message)) {
        printf("Message was already present initially, re-try the test with a different message\n");
    } else {
        printf("Message is not there initially\n");
    }
    assert(!check_message_exists(response, message));


    // POST a new message
    printf("\nPosting new message: %s\n", message);
    snprintf(post_request, sizeof(post_request),
         "POST /api/messages HTTP/1.1\r\n"
         "Cookie: username=%s\r\n"
         "Content-Type: application/json\r\n"
         "Content-Length: %zu\r\n\r\n"
         "{\"message\":\"%s\"}",
         username, strlen(message) + 13, message);

    socket= start_socket(host, port);
    if (send(socket, post_request, strlen(post_request), 0) < 0) {
        printf("Unable to send post request\n");
        close(socket);
        return;
    }
    close(socket);

    // Fetch the messages again to verify the message was posted
    printf("\nVerifying message existence on server\n");
    socket= start_socket(host, port);

    if (send(socket, fetch_request, strlen(fetch_request), 0) < 0) {
        printf("Unable to send second fetch request\n");
        close(socket);
        return;
    }

   if ((size = recv(socket, response, sizeof(response), 0)) <= 0) {
        printf("Error while receiving server's messages\n");
        close(socket);
        return;
    }
    response[size] = '\0';
    close(socket);

   if (check_message_exists(response, message)) {
        printf("Message is there after posting\n");
    } else {
        printf("Message is not there after posting\n");
    }
     // Verify that the chat message was accepted properly
    assert(check_message_exists(response, message));

    // Testing without cookies
    printf("\nTesting unauthorized access without cookie\n");
    snprintf(fetch_request, sizeof(fetch_request),
             "GET /api/messages HTTP/1.1\r\n\r\n");

    socket= start_socket(host, port);

    if (send(socket, fetch_request, strlen(fetch_request), 0) < 0) {
        printf("Unable to send unauthorized fetch request\n");
        close(socket);
        return;
    }

  if ((size = recv(socket, response, sizeof(response), 0)) <= 0) {
        printf("Error while receiving server's messages\n");
        close(socket);
        return;
    }
    response[size] = '\0';
    close(socket);

    // Check for unauthorized in the response when no cookie is set
    if (strstr(response, "401 Unauthorized")) {
        printf("Unauthorized response received as expected\n");
    } else {
        printf("Error: Unauthorized response not received\n");
    }

    assert(strstr(response, "401 Unauthorized"));

}

int main(int argc, char *argv[]) {
    if (argc < 5) {
        fprintf(stderr, "Usage: %s [host] [port] [username] [chat]\n", argv[0]);
        return -1;
    }
    const char *host = argv[1];
    int port = atoi(argv[2]);
    const char *username = argv[3];
    const char *message = argv[4];


    run_test(host, port,username, message);
    return 0;
}
