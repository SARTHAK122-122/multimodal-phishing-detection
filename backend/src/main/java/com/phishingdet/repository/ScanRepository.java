package com.phishingdet.repository;

import com.phishingdet.entity.Scan;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;

public interface ScanRepository extends JpaRepository<Scan, Long> {

    /**
     * Scans a signed-in user may see: their own, plus unattributed ones
     * (anonymous API/extension scans and the flagged seed demo rows, which
     * belong to no account and act as shared device scans).
     */
    @Query("select s from Scan s where s.user is null or s.user.id = :userId "
            + "order by s.submittedAt desc")
    Page<Scan> findVisiblePage(@Param("userId") Long userId, Pageable pageable);

    @Query("select s from Scan s where s.user is null or s.user.id = :userId "
            + "order by s.submittedAt desc")
    List<Scan> findVisibleTop(@Param("userId") Long userId, Pageable pageable);

    /**
     * NOTE: do not JOIN FETCH both {@code modalityResults} and {@code evidence}
     * in one query - both are Hibernate bags and fetching two bags at once
     * throws MultipleBagFetchException. ScanService.get() runs inside a
     * read-only transaction and lazy-loads each collection separately instead.
     */
}
