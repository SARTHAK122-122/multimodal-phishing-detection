package com.phishingdet.service;

import com.phishingdet.entity.User;
import com.phishingdet.repository.UserRepository;
import org.springframework.security.authentication.AnonymousAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;

import java.util.Optional;

/**
 * Resolves the signed-in user for the current request, or empty for an
 * anonymous caller (the browser extension, curl, or a logged-out visitor).
 * Never treats the framework's anonymous marker as a real session.
 */
@Component
public class CurrentUserService {

    private final UserRepository userRepository;

    public CurrentUserService(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    public Optional<User> current() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !auth.isAuthenticated() || auth instanceof AnonymousAuthenticationToken) {
            return Optional.empty();
        }
        String name = auth.getName();
        if (name == null || name.isBlank()) {
            return Optional.empty();
        }
        return userRepository.findByUsername(name);
    }

    /** Owner id for newly created scans: null when the caller is anonymous. */
    public Long currentIdOrNull() {
        return current().map(User::getId).orElse(null);
    }
}
