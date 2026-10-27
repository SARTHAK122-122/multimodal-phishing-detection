package com.phishingdet.repository;

import com.phishingdet.entity.ModelVersion;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface ModelVersionRepository extends JpaRepository<ModelVersion, Long> {
    Optional<ModelVersion> findFirstByModelNameOrderByVersionDesc(String modelName);
    List<ModelVersion> findAllByOrderByIdAsc();
}
