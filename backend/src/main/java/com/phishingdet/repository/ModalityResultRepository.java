package com.phishingdet.repository;

import com.phishingdet.entity.ModalityResult;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface ModalityResultRepository extends JpaRepository<ModalityResult, Long> {
    List<ModalityResult> findByScanIdOrderByModality(Long scanId);
}
