package com.phishingdet.exception;

/** Raised when a dependency (Python AI service, filesystem) fails (HTTP 502/503). */
public class ExternalServiceException extends RuntimeException {
    private final int httpStatus;

    public ExternalServiceException(String message, int httpStatus) {
        super(message);
        this.httpStatus = httpStatus;
    }

    public ExternalServiceException(String message) {
        this(message, 502);
    }

    public int getHttpStatus() {
        return httpStatus;
    }
}
