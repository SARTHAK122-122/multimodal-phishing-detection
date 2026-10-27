package com.phishingdet.dto;

import com.phishingdet.entity.User;

import java.time.ZonedDateTime;

/**
 * The authenticated user as the UI sees it. Deliberately contains NO password
 * hash - the hash never leaves the server.
 */
public record UserDto(
        Long id,
        String username,
        String email,
        String displayName,
        String role,
        ZonedDateTime createdAt,
        ZonedDateTime lastLoginAt) {

    public static UserDto from(User u) {
        return new UserDto(
                u.getId(), u.getUsername(), u.getEmail(),
                u.getShownName(), u.getRole().name(),
                u.getCreatedAt(), u.getLastLoginAt());
    }
}
