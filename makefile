CC = gcc
CFLAGS = -Wall -g
TARGET = scraper_client

$(TARGET): scraper_client.c
	$(CC) $(CFLAGS) -o $(TARGET) scraper_client.c

clean:
	rm -f $(TARGET)
