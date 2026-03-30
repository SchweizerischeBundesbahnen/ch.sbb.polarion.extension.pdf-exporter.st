package com.polarion.demo;

import junit.framework.TestCase;

public class LibraryTest extends TestCase {

    public void testLibrarySize() {
        Library library = new Library();
        assertEquals("Unexpected library size", 0, library.getSize());

        Book firstBook = new Book("The C Programming Language", "Kernighan & Ritchie", "Jackson", 1996);
        library.add(firstBook);
        assertEquals("Unexpected library size", 1, library.getSize());

        Book secondBook = new Book("C C++ Programmer's Reference Third Edition", "Herbert Schildt", "JacksonMcGraw-Hill", 2003);
        library.add(secondBook);
        assertEquals("Unexpected library size", 2, library.getSize());
    }

    public void testLibrarySearch() {
        Library library = new Library();

        Book firstBook = new Book("The C Programming Language", "Kernighan & Ritchie", "Jackson", 1996);
        library.add(firstBook);

        Book secondBook = new Book("C C++ Programmer's Reference Third Edition", "Herbert Schildt", "JacksonMcGraw-Hill", 2003);
        library.add(secondBook);

        Book[] programBooks = library.search("Program");
        assertEquals("Unexpected search result size", 2, programBooks.length);

        Book[] kernighanBooks = library.search("Kernighan");
        assertEquals("Unexpected search result size", 1, kernighanBooks.length);

        assertEquals("Unexpected search result", firstBook, kernighanBooks[0]);
    }


}
