package com.phishingdet.controller;

import com.phishingdet.dto.AuthRequest;
import com.phishingdet.dto.UserDto;
import com.phishingdet.entity.User;
import com.phishingdet.exception.UnauthorizedException;
import com.phishingdet.service.AuthService;
import com.phishingdet.service.CurrentUserService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * Authentication endpoints backing the login/register/profile pages.
 *
 * <pre>
 * POST /api/auth/register        create account + sign in (first real account = ADMIN)
 * POST /api/auth/login           verify credentials + start session
 * POST /api/auth/logout          end session
 * GET  /api/auth/me              current user, or 401 when signed out
 * POST /api/auth/change-password requires session; current password required
 * PATCH /api/auth/profile        update display name / email
 * </pre>
 *
 * <p>Responses never contain the password hash. Failed logins all return the
 * same generic 401 message (no username enumeration).</p>
 */
@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final AuthService authService;
    private final CurrentUserService currentUserService;

    public AuthController(AuthService authService, CurrentUserService currentUserService) {
        this.authService = authService;
        this.currentUserService = currentUserService;
    }

    @PostMapping("/register")
    public ResponseEntity<UserDto> register(@Valid @RequestBody AuthRequest.Register request,
                                            HttpServletRequest httpReq,
                                            HttpServletResponse httpResp) {
        User user = authService.register(request);
        authService.establishSession(user, httpReq, httpResp);
        return ResponseEntity.status(HttpStatus.CREATED).body(UserDto.from(user));
    }

    @PostMapping("/login")
    public UserDto login(@Valid @RequestBody AuthRequest.Login request,
                         HttpServletRequest httpReq,
                         HttpServletResponse httpResp) {
        return UserDto.from(authService.login(request, httpReq, httpResp));
    }

    @PostMapping("/logout")
    public Map<String, Object> logout(HttpServletRequest httpReq, HttpServletResponse httpResp) {
        authService.endSession(httpReq, httpResp);
        return Map.of("ok", true);
    }

    @GetMapping("/me")
    public UserDto me() {
        User user = currentUserService.current()
                .orElseThrow(() -> new UnauthorizedException("Sign in to continue."));
        return UserDto.from(user);
    }

    @PostMapping("/change-password")
    public Map<String, Object> changePassword(@Valid @RequestBody AuthRequest.ChangePassword request) {
        User user = currentUserService.current()
                .orElseThrow(() -> new UnauthorizedException("Sign in to continue."));
        authService.changePassword(user, request);
        return Map.of("ok", true);
    }

    @PatchMapping("/profile")
    public UserDto updateProfile(@Valid @RequestBody AuthRequest.ProfileUpdate request) {
        User user = currentUserService.current()
                .orElseThrow(() -> new UnauthorizedException("Sign in to continue."));
        return UserDto.from(authService.updateProfile(user, request));
    }
}
