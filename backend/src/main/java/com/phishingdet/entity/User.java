package com.phishingdet.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;

import java.time.ZonedDateTime;

/**
 * Application user.
 *
 * <p><b>Authentication is implemented:</b> passwords are stored only as BCrypt
 * hashes written by Spring Security, login is a server-side HTTP session, and
 * the ADMIN role gates the research workspace. The two seeded demo users from
 * V2 still carry sentinel hashes and therefore <b>cannot log in</b> - they exist
 * only to demonstrate the flagged seed rows.</p>
 *
 * <p>Not implemented (documented gap, not faked): password reset, email
 * verification, account lockout.</p>
 */
@Entity
@Table(name = "users")
public class User {

    public enum Role { USER, ADMIN }

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 50)
    private String username;

    @Column(nullable = false, unique = true)
    private String email;

    /** Optional profile name shown in the UI; falls back to the username. */
    @Column(name = "display_name", length = 100)
    private String displayName;

    /** BCrypt hash ($2a/$2b...). Sentinel values (seed users) cannot authenticate. */
    @Column(name = "password_hash", nullable = false, length = 255)
    private String passwordHash = "SENTINEL-NO-AUTH-IMPLEMENTED";

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private Role role = Role.USER;

    @Column(name = "last_login_at")
    private ZonedDateTime lastLoginAt;

    @Column(name = "created_at", nullable = false, updatable = false)
    private ZonedDateTime createdAt;

    @PrePersist
    void onCreate() {
        if (createdAt == null) {
            createdAt = ZonedDateTime.now(java.time.ZoneOffset.UTC);
        }
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }
    public String getEmail() { return email; }
    public void setEmail(String email) { this.email = email; }
    public String getPasswordHash() { return passwordHash; }
    public void setPasswordHash(String passwordHash) { this.passwordHash = passwordHash; }
    public Role getRole() { return role; }
    public void setRole(Role role) { this.role = role; }
    public String getDisplayName() { return displayName; }
    public void setDisplayName(String displayName) { this.displayName = displayName; }
    public ZonedDateTime getLastLoginAt() { return lastLoginAt; }
    public void setLastLoginAt(ZonedDateTime lastLoginAt) { this.lastLoginAt = lastLoginAt; }
    public ZonedDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(ZonedDateTime createdAt) { this.createdAt = createdAt; }

    /** Name shown in the UI: profile name when set, otherwise the username. */
    public String getShownName() {
        return displayName == null || displayName.isBlank() ? username : displayName;
    }
}
