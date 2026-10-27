package com.phishingdet.controller;

import com.phishingdet.dto.AuthRequest;
import com.phishingdet.entity.User;
import com.phishingdet.exception.BadRequestException;
import com.phishingdet.exception.GlobalExceptionHandler;
import com.phishingdet.exception.UnauthorizedException;
import com.phishingdet.repository.UserRepository;
import com.phishingdet.service.AuthService;
import com.phishingdet.service.CurrentUserService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.context.SecurityContextRepository;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.validation.beanvalidation.LocalValidatorFactoryBean;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Authentication contract tests: registration validation, BCrypt-only storage,
 * first-account-admin rule, generic failed-login message (no username
 * enumeration), sentinel seed users rejected before the password encoder is
 * consulted, and the session being saved on successful login.
 *
 * <p>The database, AuthenticationManager and session repository are mocked -
 * this suite verifies what the controller/service own, in the same standalone
 * MockMvc style as {@link ScanControllerTest}.</p>
 */
class AuthControllerTest {

    private UserRepository userRepository;
    private AuthenticationManager authenticationManager;
    private SecurityContextRepository securityContextRepository;
    private CurrentUserService currentUserService;
    private PasswordEncoder encoder;
    private MockMvc mvc;

    @BeforeEach
    void setUp() {
        userRepository = mock(UserRepository.class);
        authenticationManager = mock(AuthenticationManager.class);
        securityContextRepository = mock(SecurityContextRepository.class);
        currentUserService = mock(CurrentUserService.class);
        encoder = new BCryptPasswordEncoder(4); // low cost keeps the suite fast

        AuthService authService = new AuthService(
                userRepository, encoder, authenticationManager, securityContextRepository);

        LocalValidatorFactoryBean validator = new LocalValidatorFactoryBean();
        validator.afterPropertiesSet();

        mvc = MockMvcBuilders
                .standaloneSetup(new AuthController(authService, currentUserService))
                .setControllerAdvice(new GlobalExceptionHandler())
                .setValidator(validator)
                .build();

        when(currentUserService.current()).thenReturn(Optional.empty());
    }

    private User existingUser(String username, String rawPassword) {
        User u = new User();
        u.setId(5L);
        u.setUsername(username);
        u.setEmail(username + "@example.com");
        u.setPasswordHash(rawPassword == null ? "SENTINEL-NO-AUTH-IMPLEMENTED" : encoder.encode(rawPassword));
        u.setRole(User.Role.USER);
        return u;
    }

    /* ---------------------------- registration --------------------------- */

    @Test
    void firstRealAccountIsCreatedAsAdminWithBcryptHashOnly() throws Exception {
        when(userRepository.findByUsername("alice")).thenReturn(Optional.empty());
        when(userRepository.findByEmail("alice@example.com")).thenReturn(Optional.empty());
        when(userRepository.existsByRoleAndPasswordHashStartingWith(User.Role.ADMIN, "$2"))
                .thenReturn(false);
        when(userRepository.save(any(User.class))).thenAnswer(inv -> {
            User u = inv.getArgument(0);
            u.setId(1L);
            return u;
        });

        mvc.perform(post("/api/auth/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"alice\",\"email\":\"alice@example.com\","
                                + "\"displayName\":\"Alice\",\"password\":\"correct-horse-1\"}"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.username").value("alice"))
                .andExpect(jsonPath("$.role").value("ADMIN"))
                .andExpect(jsonPath("$.passwordHash").doesNotExist());

        ArgumentCaptor<User> saved = ArgumentCaptor.forClass(User.class);
        verify(userRepository).save(saved.capture());
        // Stored value must be a bcrypt hash of the password, never the password.
        assertThat(saved.getValue().getPasswordHash()).startsWith("$2");
        assertThat(saved.getValue().getPasswordHash()).isNotEqualTo("correct-horse-1");
        assertThat(encoder.matches("correct-horse-1", saved.getValue().getPasswordHash())).isTrue();
    }

    @Test
    void laterAccountsBecomePlainUsers() throws Exception {
        when(userRepository.findByUsername("bob")).thenReturn(Optional.empty());
        when(userRepository.findByEmail("bob@example.com")).thenReturn(Optional.empty());
        when(userRepository.existsByRoleAndPasswordHashStartingWith(User.Role.ADMIN, "$2"))
                .thenReturn(true); // an admin already exists
        when(userRepository.save(any(User.class))).thenAnswer(inv -> {
            User u = inv.getArgument(0);
            u.setId(2L);
            return u;
        });

        mvc.perform(post("/api/auth/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"bob\",\"email\":\"bob@example.com\","
                                + "\"password\":\"another-pass-9\"}"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.role").value("USER"));
    }

    @Test
    void registerRejectsShortPasswordWith400() throws Exception {
        mvc.perform(post("/api/auth/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"carol\",\"email\":\"carol@example.com\","
                                + "\"password\":\"short\"}"))
                .andExpect(status().isBadRequest());

        verify(userRepository, never()).save(any(User.class));
    }

    @Test
    void registerRejectsDuplicateUsernameWith400() throws Exception {
        when(userRepository.findByUsername("taken")).thenReturn(Optional.of(existingUser("taken", "x")));

        mvc.perform(post("/api/auth/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"taken\",\"email\":\"new@example.com\","
                                + "\"password\":\"valid-pass-12\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("That username is already taken."));
    }

    /* -------------------------------- login ------------------------------ */

    @Test
    void wrongPasswordReturnsGeneric401WithoutUserEnumeration() throws Exception {
        when(userRepository.findByUsername("dave")).thenReturn(
                Optional.of(existingUser("dave", "real-password-1")));
        // The real AuthenticationManager (DaoAuthenticationProvider) throws on a
        // password mismatch; reproduce that here.
        when(authenticationManager.authenticate(any()))
                .thenThrow(new BadCredentialsException("bad credentials"));

        mvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"dave\",\"password\":\"wrong-password\"}"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.message").value("Invalid username or password."));

        // The manager was consulted (and rejected the password) but no session
        // was ever created.
        verify(authenticationManager).authenticate(any());
        verify(securityContextRepository, never()).saveContext(any(), any(), any());
    }

    @Test
    void unknownUsernameReturnsTheSameGeneric401() throws Exception {
        when(userRepository.findByUsername("ghost")).thenReturn(Optional.empty());

        mvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"ghost\",\"password\":\"whatever-123\"}"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.message").value("Invalid username or password."));
    }

    @Test
    void sentinelSeedUserCannotLogInAndNeverReachesThePasswordEncoder() throws Exception {
        when(userRepository.findByUsername("demo_admin")).thenReturn(
                Optional.of(existingUser("demo_admin", null))); // sentinel hash

        mvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"demo_admin\",\"password\":\"anything-123\"}"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.message").value("Invalid username or password."));

        verify(authenticationManager, never()).authenticate(any());
    }

    @Test
    void successfulLoginReturnsUserAndSavesTheSession() throws Exception {
        User dave = existingUser("dave", "real-password-1");
        when(userRepository.findByUsername("dave")).thenReturn(Optional.of(dave));
        when(userRepository.save(any(User.class))).thenAnswer(inv -> inv.getArgument(0));

        mvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"dave\",\"password\":\"real-password-1\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.username").value("dave"))
                .andExpect(jsonPath("$.passwordHash").doesNotExist());

        verify(authenticationManager).authenticate(any());
        verify(securityContextRepository).saveContext(any(), any(), any());
        assertThat(dave.getLastLoginAt()).isNotNull();
    }

    /* -------------------------- session endpoints ------------------------ */

    @Test
    void meWithoutSessionReturns401() throws Exception {
        when(currentUserService.current()).thenReturn(Optional.empty());

        mvc.perform(get("/api/auth/me"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.message").value("Sign in to continue."));
    }

    @Test
    void meWithSessionReturnsTheUser() throws Exception {
        when(currentUserService.current()).thenReturn(Optional.of(existingUser("dave", "p-12345678")));

        mvc.perform(get("/api/auth/me"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.username").value("dave"));
    }

    /* --------------------------- password change ------------------------- */

    @Test
    void changePasswordRequiresCorrectCurrentPassword() throws Exception {
        User dave = existingUser("dave", "real-password-1");
        when(currentUserService.current()).thenReturn(Optional.of(dave));

        mvc.perform(post("/api/auth/change-password")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"currentPassword\":\"not-the-one\","
                                + "\"newPassword\":\"brand-new-pass-1\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("The current password is incorrect."));

        // Hash must be untouched.
        assertThat(encoder.matches("real-password-1", dave.getPasswordHash())).isTrue();
    }

    @Test
    void changePasswordStoresANewBcryptHash() throws Exception {
        User dave = existingUser("dave", "real-password-1");
        when(currentUserService.current()).thenReturn(Optional.of(dave));
        when(userRepository.save(any(User.class))).thenAnswer(inv -> inv.getArgument(0));

        mvc.perform(post("/api/auth/change-password")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"currentPassword\":\"real-password-1\","
                                + "\"newPassword\":\"brand-new-pass-1\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true));

        assertThat(encoder.matches("brand-new-pass-1", dave.getPasswordHash())).isTrue();
        assertThat(encoder.matches("real-password-1", dave.getPasswordHash())).isFalse();
    }

    /* ------------------------------ profile ------------------------------ */

    @Test
    void profileUpdateChangesDisplayNameAndEmail() throws Exception {
        User dave = existingUser("dave", "real-password-1");
        when(currentUserService.current()).thenReturn(Optional.of(dave));
        when(userRepository.findByEmail("new@example.com")).thenReturn(Optional.empty());
        when(userRepository.save(any(User.class))).thenAnswer(inv -> inv.getArgument(0));

        mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders
                        .patch("/api/auth/profile")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"displayName\":\"David\",\"email\":\"new@example.com\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.displayName").value("David"))
                .andExpect(jsonPath("$.email").value("new@example.com"));
    }

    @Test
    void profileUpdateRejectsEmailOwnedByAnotherAccount() throws Exception {
        User dave = existingUser("dave", "real-password-1");
        dave.setId(5L);
        when(currentUserService.current()).thenReturn(Optional.of(dave));
        User other = existingUser("other", "x");
        other.setId(9L);
        when(userRepository.findByEmail("busy@example.com")).thenReturn(Optional.of(other));

        mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders
                        .patch("/api/auth/profile")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"email\":\"busy@example.com\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("That email is already registered."));
    }
}
