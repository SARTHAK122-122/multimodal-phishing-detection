package com.phishingdet.repository;

import com.phishingdet.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface UserRepository extends JpaRepository<User, Long> {

    Optional<User> findByUsername(String username);

    Optional<User> findByEmail(String email);

    /**
     * True when at least one ADMIN can actually authenticate (BCrypt hashes start
     * with "$2"). The V2 seed admin carries a sentinel hash and can never log in,
     * so the first real registration still becomes the administrator.
     */
    boolean existsByRoleAndPasswordHashStartingWith(User.Role role, String prefix);
}
