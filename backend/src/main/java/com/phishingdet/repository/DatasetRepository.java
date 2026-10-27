package com.phishingdet.repository;

import com.phishingdet.entity.Dataset;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface DatasetRepository extends JpaRepository<Dataset, Long> {
    List<Dataset> findAllByOrderByUploadedAtDesc();
}
