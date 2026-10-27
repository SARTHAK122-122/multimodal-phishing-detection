package com.phishingdet.repository;

import com.phishingdet.entity.PreprocessingRun;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface PreprocessingRunRepository extends JpaRepository<PreprocessingRun, Long> {

    /**
     * The dataset association is LAZY; every read path builds a DTO, so fetch
     * the graph eagerly to avoid LazyInitializationException once the short
     * repository transaction closes (the service methods are intentionally NOT
     * transactional around the Python HTTP call).
     */
    @Override
    @EntityGraph(attributePaths = "dataset")
    Optional<PreprocessingRun> findById(Long id);

    @Override
    @EntityGraph(attributePaths = "dataset")
    List<PreprocessingRun> findAll();

    @EntityGraph(attributePaths = "dataset")
    List<PreprocessingRun> findByDatasetIdOrderByStartedAtDesc(Long datasetId);
}
