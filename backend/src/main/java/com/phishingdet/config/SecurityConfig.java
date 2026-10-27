package com.phishingdet.config;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpStatus;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.context.HttpSessionSecurityContextRepository;
import org.springframework.security.web.context.RequestAttributeSecurityContextRepository;
import org.springframework.security.web.context.SecurityContextRepository;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.io.IOException;
import java.time.Instant;
import java.util.Arrays;
import java.util.List;

/**
 * Real authentication for the platform.
 *
 * <p><b>Access rules</b> (single source of truth for who may call what):</p>
 * <ul>
 *   <li>login/register - open (they create the session)</li>
 *   <li>POST /api/scans* - open, because the Chrome extension posts scans
 *       anonymously and the API has always allowed analysis without an
 *       account; when a session exists the scan is saved to that user</li>
 *   <li>GET /api/health - open, used by ops checks and Docker healthchecks</li>
 *   <li>datasets / preprocessing / models / evaluations - ADMIN only: the
 *       research workspace is now genuinely access-controlled</li>
 *   <li>every other /api/** route - any signed-in user</li>
 * </ul>
 *
 * <p><b>Sessions</b> are server-side HTTP sessions (JSESSIONID, HttpOnly,
 * SameSite=Lax) - no token is ever stored in browser JavaScript. CSRF is
 * disabled deliberately: every state-changing endpoint consumes/produces JSON
 * (no form POSTs) and the session cookie is SameSite=Lax, which modern browsers
 * do not attach to cross-site state-changing requests. This trade-off is
 * documented in the README rather than silently assumed.</p>
 */
@Configuration
@EnableWebSecurity
@EnableMethodSecurity
public class SecurityConfig {

    private final String[] allowedOrigins;

    public SecurityConfig(@Value("${app.cors.allowed-origins}") String[] allowedOrigins) {
        this.allowedOrigins = allowedOrigins;
    }

    /** Shared with the login endpoint so login/session storage is one mechanism. */
    @Bean
    public SecurityContextRepository securityContextRepository() {
        return new org.springframework.security.web.context.DelegatingSecurityContextRepository(
                new RequestAttributeSecurityContextRepository(),
                new HttpSessionSecurityContextRepository());
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    /**
     * Exposes the AuthenticationManager (built from the UserDetailsService +
     * PasswordEncoder) so AuthService can verify credentials on login.
     */
    @Bean
    public org.springframework.security.authentication.AuthenticationManager authenticationManager(
            org.springframework.security.config.annotation.authentication.configuration.AuthenticationConfiguration configuration)
            throws Exception {
        return configuration.getAuthenticationManager();
    }

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http,
                                                   SecurityContextRepository securityContextRepository)
            throws Exception {
        http
            // JSON API + Sameite=Lax session cookie; see class javadoc.
            .csrf(csrf -> csrf.disable())
            .cors(cors -> cors.configurationSource(corsConfigurationSource()))
            .securityContext(c -> c.securityContextRepository(securityContextRepository))
            .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.IF_REQUIRED))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/auth/register", "/api/auth/login").permitAll()
                .requestMatchers(
                        org.springframework.http.HttpMethod.POST,
                        "/api/scans", "/api/scans/website", "/api/scans/email",
                        "/api/scans/sms", "/api/scans/qr").permitAll()
                .requestMatchers("/api/health", "/api/health/**").permitAll()
                .requestMatchers(
                        "/api/datasets/**", "/api/preprocessing-runs/**",
                        "/api/models/**", "/api/evaluations/**").hasRole("ADMIN")
                .requestMatchers("/api/**").authenticated()
                .anyRequest().permitAll())
            .exceptionHandling(e -> e
                .authenticationEntryPoint(this::writeUnauthorized)
                .accessDeniedHandler(this::writeForbidden))
            .formLogin(f -> f.disable())
            .httpBasic(b -> b.disable())
            .logout(l -> l.disable()); // logout is POST /api/auth/logout (own endpoint)
        return http.build();
    }

    private CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration cfg = new CorsConfiguration();
        cfg.setAllowedOrigins(Arrays.asList(allowedOrigins));
        cfg.setAllowedMethods(List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
        cfg.setAllowedHeaders(List.of("*"));
        cfg.setMaxAge(3600L);
        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", cfg);
        return source;
    }

    private void writeUnauthorized(HttpServletRequest req, HttpServletResponse res,
                                   org.springframework.security.core.AuthenticationException ex)
            throws IOException {
        writeJson(res, HttpStatus.UNAUTHORIZED, "authentication_required", "Sign in to continue.");
    }

    private void writeForbidden(HttpServletRequest req, HttpServletResponse res,
                                org.springframework.security.access.AccessDeniedException ex)
            throws IOException {
        writeJson(res, HttpStatus.FORBIDDEN, "forbidden",
                "This area requires an administrator account.");
    }

    private void writeJson(HttpServletResponse res, HttpStatus status, String error, String message)
            throws IOException {
        res.setStatus(status.value());
        res.setContentType("application/json");
        res.setCharacterEncoding("UTF-8");
        // Constant strings only - nothing user-controlled is interpolated.
        res.getWriter().write("{\"timestamp\":\"" + Instant.now()
                + "\",\"status\":" + status.value()
                + ",\"error\":\"" + error + "\",\"message\":\"" + message + "\"}");
    }
}
