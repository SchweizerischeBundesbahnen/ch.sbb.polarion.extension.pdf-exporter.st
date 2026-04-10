/* Small Example class */

package com.polarion.demo;

public class Example {

    public static void main(String[] args) {
        Book myFirstBook = new Book("The C Programming Language", "Kernighan & Ritchie", "Jackson", 1996);
        Library myLibrary = new Library();
        myLibrary.add(myFirstBook);
        myLibrary.add(new Book("C C++ Programmer's Reference Third Edition", "Herbert Schildt", "JacksonMcGraw-Hill", 2003));
        Book[] results = myLibrary.search("mme");
        if (results.length == 0) {
            System.out.println("Sorry, No Results Found");
        } else {
            for (int i=0; i<results.length; i++)
                System.out.println(results[i].getTitle());
        }
    }

}
