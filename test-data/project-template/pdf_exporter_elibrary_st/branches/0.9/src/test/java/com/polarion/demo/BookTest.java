package com.polarion.demo;

import junit.framework.TestCase;

public class BookTest extends TestCase {

    public void testBook() {
        String title = "The C Programming Language";
        String author = "Kernighan & Ritchie";
        String publisher = "Jackson";
        int year = 1996;
        Book book = new Book(title, author, publisher, year);

        assertEquals("Wrong book author", author, book.getAuthor());
        assertEquals("Unexpected book title", title, book.getTitle());
        assertEquals("Unexpected book publisher", publisher, book.getPublisher());
        assertEquals("Unexpected book publication year", year, book.getPublicationYear());
    }

}
