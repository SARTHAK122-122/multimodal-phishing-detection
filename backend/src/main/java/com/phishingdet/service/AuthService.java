package com.phishingdet.service;

import com.phishingdet.entity.User;
import com.phishingdet.repository.UserRepository;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.context.SecurityContextRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.phishingdet.dto.AuthRequest;
import com.phishingdet.exception.BadRequestException;
import com.phishingdet.exception.UnauthorizedException;

import java.time.ZoneOffset;
import java.time.ZonedDateTime;

/**
 * Registration, login, password change and profile update.
 *
 * <p>Security-relevant behaviour:</p>
 * <ul>
 *   <li>passwords are BCrypt-hashed on write and only checked with
 *       {@link PasswordEncoder#matches} - plaintext is never stored or
 *       logged;</li>
 *   <li>failed logins return one generic message so the API does not reveal
 *       whether a username exists;</li>
 *   <li>login/register establish the session by saving the security context
 *       through the same repository the filter chain reads, so the very next
 *       request is authenticated;</li>
 *   <li>the first account registered on a fresh database becomes ADMIN: the V2
 *       seed "demo_admin" carries a sentinel hash and can never log in, so a
 *       demo deployment still ends up with a real administrator.</li>
 * </ul>
 */
@Service
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final AuthenticationManager authenticationManager;
    private final SecurityContextRepository securityContextRepository;

    public AuthService(UserRepository userRepository,
                       PasswordEncoder passwordEncoder,
                       AuthenticationManager authenticationManager,
                       SecurityContextRepository securityContextRepository) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.authenticationManager = authenticationManager;
        this.securityContextRepository = securityContextRepository;
    }

    /** Creates the account and returns the saved entity. Session is established by the controller. */
    @Transactional
    public User register(AuthRequest.Register req) {
        String username = req.username().trim();
        if (userRepository.findByUsername(username).isPresent()) {
            throw new BadRequestException("That username is already taken.");
        }
        String email = req.email().trim();
        if (userRepository.findByEmail(email).isPresent()) {
            throw new BadRequestException("That email is already registered.");
        }

        User user = new User();
        user.setUsername(username);
        user.setEmail(email);
        String display = req.displayName() == null ? null : req.displayName().trim();
        user.setDisplayName(display == null || display.isBlank() ? null : display);
        user.setPasswordHash(passwordEncoder.encode(req.password()));
        // Registration establishes a session immediately, so it is also a
        // sign-in - record it here (login() does the same before its session).
        user.setLastLoginAt(ZonedDateTime.now(ZoneOffset.UTC));
        // First *real* account (BCrypt hash) becomes the administrator.
        user.setRole(userRepository.existsByRoleAndPasswordHashStartingWith(User.Role.ADMIN, "$2")
                ? User.Role.USER
                : User.Role.ADMIN);
        return userRepository.save(user);
    }

    /** Verifies credentials, records the login time and establishes the session. */
    @Transactional
    public User login(AuthRequest.Login req, HttpServletRequest request, HttpServletResponse response) {
        User user = userRepository.findByUsername(req.username().trim())
                .orElseThrow(() -> new UnauthorizedException("Invalid username or password."));
        // Sentinel/legacy hashes cannot authenticate; short-circuit with the same
        // generic message instead of letting BCrypt warn about an invalid hash.
        if (!user.getPasswordHash().startsWith("$2")) {
            throw new UnauthorizedException("Invalid username or password.");
        }
        try {
            authenticationManager.authenticate(
                    new UsernamePasswordAuthenticationToken(user.getUsername(), req.password()));
        } catch (AuthenticationException ex) {
            throw new UnauthorizedException("Invalid username or password.");
        }
        user.setLastLoginAt(ZonedDateTime.now(ZoneOffset.UTC));
        userRepository.save(user);
        establishSession(user, request, response);
        return user;
    }

    /** Puts an authenticated context into the session (login and register both use it). */
    public void establishSession(User user, HttpServletRequest request, HttpServletResponse response) {
        var springUser = org.springframework.security.core.userdetails.User
                .withUsername(user.getUsername())
                .password(user.getPasswordHash())
                .roles(user.getRole().name())
                .build();
        var authentication = new UsernamePasswordAuthenticationToken(
                springUser, null, springUser.getAuthorities());
        var context = org.springframework.security.core.context.SecurityContextHolder.createEmptyContext();
        context.setAuthentication(authentication);
        SecurityContextHolder.setContext(context);
        securityContextRepository.saveContext(context, request, response);
    }

    /** Clears the server-side session (POST /api/auth/logout). */
    public void endSession(HttpServletRequest request, HttpServletResponse response) {
        SecurityContextHolder.clearContext();
        jakarta.servlet.http.HttpSession session = request.getSession(false);
        if (session != null) {
            session.invalidate();
        }
        // Ensure the response also drops the security context cookie state.
        securityContextRepository.saveContext(
                org.springframework.security.core.context.SecurityContextHolder.createEmptyContext(),
                request, response);
    }

    @Transactional
    public void changePassword(User user, AuthRequest.ChangePassword req) {
        if (!passwordEncoder.matches(req.currentPassword(), user.getPasswordHash())) {
            throw new BadRequestException("The current password is incorrect.");
        }
        if (passwordEncoder.matches(req.newPassword(), user.getPasswordHash())) {
            throw new BadRequestException("Choose a password different from the current one.");
        }
        user.setPasswordHash(passwordEncoder.encode(req.newPassword()));
        userRepository.save(user);
    }

    @Transactional
    public User updateProfile(User user, AuthRequest.ProfileUpdate patch) {
        if (patch.email() != null) {
            String email = patch.email().trim();
            if (!email.isBlank()) {
                userRepository.findByEmail(email)
                        .filter(other -> !other.getId().equals(user.getId()))
                        .ifPresent(other -> {
                            throw new BadRequestException("That email is already registered.");
                        });
                user.setEmail(email);
            }
        }
        if (patch.displayName() != null) {
            String display = patch.displayName().trim();
            user.setDisplayName(display.isBlank() ? null : display);
        }
        return userRepository.save(user);
    }
}
