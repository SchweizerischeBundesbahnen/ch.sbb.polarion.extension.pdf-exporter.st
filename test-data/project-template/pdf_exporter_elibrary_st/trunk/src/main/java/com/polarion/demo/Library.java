package com.polarion.demo;

import java.util.Iterator;
import java.util.LinkedList;
import java.util.List;

public class Library {

    private List books;

    /**
     * Creates a new empty library.
     *
     */
    public Library() {
        books = new LinkedList();
    }

    /**
     * Adds a book to the library.
     *
     * @param book
     */
    public void add(Book book) {
        books.add(book);
    }

    /**
     * Removes a book from the library, if it was previously added.
     * Returns <code>true</code>, if the book was removed.
     *
     * @param book
     */
    public boolean remove(Book book) {
        return books.remove(book);
    }

    /**
     * Returns total count of books in this library.
     */
    public int getSize() {
        return books.size();
    }

    /**
     * Searches this library for books that contain the given word
     * in title, author or publisher field.
     */
    public Book[] search(String word) {
        List result = new LinkedList();
        for (Iterator iter = books.iterator(); iter.hasNext();) {
            Book book = (Book) iter.next();
            if(matches(book, word)) {
                result.add(book);
            }
        }
        return (Book[])result.toArray(new Book[result.size()]);
    }

    private boolean matches(Book book, String word) {
        return matches(book.getTitle(), word) || matches(book.getAuthor(), word) || matches(book.getPublisher(), word);
    }

    private boolean matches(String s, String word) {
        return (s != null) && s.indexOf(word) >= 0;
    }

}
