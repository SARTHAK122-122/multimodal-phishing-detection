package com.phishingdet.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

/**
 * Authentication request payloads. Validation is Bean Validation, enforced by
 * {@code @Valid} in the controller - the same style as {@code ScanRequest}.
 * Passwords travel in these records only over the request boundary and are
 * stored server-side exclusively as BCrypt hashes; they are never logged,
 * echoed back, or put into a DTO response.
 */
public final class AuthRequest {

    private AuthRequest() {
    }

    public record Register(
            @NotBlank
            @Size(min = 3, max = 50)
            @Pattern(regexp = "^[A-Za-z0-9_.\\-]+$",
                    message = "may only contain letters, digits, underscore, dot and hyphen")
            String username,

            @NotBlank
            @Email
            @Size(max = 255)
            String email,

            @Size(max = 100)
            String displayName,

            @NotBlank
            @Size(min = 8, max = 72, message = "must be between 8 and 72 characters")
            String password) {
    }

    public record Login(
            @NotBlank String username,
            @NotBlank String password) {
    }

    public record ChangePassword(
            @NotBlank String currentPassword,
            @NotBlank
            @Size(min = 8, max = 72, message = "must be between 8 and 72 characters")
            String newPassword) {
    }

    public record ProfileUpdate(
            @Size(max = 100) String displayName,
            @Email @Size(max = 255) String email) {
    }
}
