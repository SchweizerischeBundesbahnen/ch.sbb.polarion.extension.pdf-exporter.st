package com.polarion.demo;

import junit.framework.TestCase;

/**
 * LoginTest always fails, it is executed if you select "All Tests" build definition when
 * creating a new build using polarion
 */
public class LoginTest extends TestCase {

    public void testLogin() {
        assertTrue("Cannot login as Karl Xavier", false);
    }

    public void testLogout() {
       throw new RuntimeException("Cannot logout, no logged in user");
    }

}
