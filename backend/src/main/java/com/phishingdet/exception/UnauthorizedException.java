package com.phishingdet.exception;

/** 401 - the caller must sign in (or presented wrong credentials). */
public class UnauthorizedException extends RuntimeException {
    public UnauthorizedException(String message) {
        super(message);
    }
}
