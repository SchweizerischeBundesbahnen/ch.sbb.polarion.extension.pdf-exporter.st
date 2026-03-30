package com.polarion.demo;


public class Book {

    private String title;
    private String author;
    private String publisher;
    private int publicationYear;

    /**
     * Creates a new book.
     *
     * @param title
     * @param author
     * @param publisher
     * @param publicationYear
     */
    public Book(String title, String author, String publisher, int publicationYear) {
        this.title = title;
        this.author = author;
        this.publisher = publisher;
        this.publicationYear = publicationYear;
    }

    /**
     * Returns title of this book.
     */
    public String getTitle() {
        return this.title;
    }

    /**
     * Returns author of this book.
     */
    public String getAuthor() {
        return this.author;
    }

    /**
     * Returns publisher of this book.
     */
    public String getPublisher() {
        return this.publisher;
    }

    /**
     * Returns publication year of this book.
     */
    public int getPublicationYear() {
        return this.publicationYear;
    }

}
