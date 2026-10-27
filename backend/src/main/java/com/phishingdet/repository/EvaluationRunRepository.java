package com.phishingdet.repository;

import com.phishingdet.entity.EvaluationRun;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface EvaluationRunRepository extends JpaRepository<EvaluationRun, Long> {
    List<EvaluationRun> findAllByOrderByEvaluationDateDesc();
}
