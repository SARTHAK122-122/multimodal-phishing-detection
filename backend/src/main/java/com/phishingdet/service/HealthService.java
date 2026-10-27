package com.phishingdet.service;

import com.phishingdet.dto.HealthResponse;
import com.phishingdet.dto.HealthResponse.DatabaseHealth;
import com.phishingdet.repository.DatasetRepository;
import com.phishingdet.repository.EvaluationRunRepository;
import com.phishingdet.repository.ModelVersionRepository;
import com.phishingdet.repository.PreprocessingRunRepository;
import com.phishingdet.repository.ScanRepository;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Health check: verifies the live PostgreSQL connection, reports table row
 * counts, and probes the Python AI service without failing the whole endpoint
 * when only one component is down.
 */
@Service
public class HealthService {

    private final DataSource dataSource;
    private final ScanRepository scanRepository;
    private final DatasetRepository datasetRepository;
    private final PreprocessingRunRepository preprocessingRunRepository;
    private final ModelVersionRepository modelVersionRepository;
    private final EvaluationRunRepository evaluationRunRepository;
    private final RestClient aiClient;
    private final String aiBaseUrl;

    public HealthService(DataSource dataSource,
                         ScanRepository scanRepository,
                         DatasetRepository datasetRepository,
                         PreprocessingRunRepository preprocessingRunRepository,
                         ModelVersionRepository modelVersionRepository,
                         EvaluationRunRepository evaluationRunRepository,
                         @Value("${ai.service.base-url}") String aiBaseUrl,
                         @Value("${ai.service.connect-timeout-ms}") int connectTimeoutMs,
                         @Value("${ai.service.read-timeout-ms}") int readTimeoutMs) {
        this.dataSource = dataSource;
        this.scanRepository = scanRepository;
        this.datasetRepository = datasetRepository;
        this.preprocessingRunRepository = preprocessingRunRepository;
        this.modelVersionRepository = modelVersionRepository;
        this.evaluationRunRepository = evaluationRunRepository;
        this.aiBaseUrl = aiBaseUrl;
        this.aiClient = RestClient.builder()
                .baseUrl(aiBaseUrl)
                .build();
    }

    public HealthResponse health() {
        DatabaseHealth db = checkDatabase();
        DatabaseHealth ai = checkAiService();

        Map<String, Long> counts = new LinkedHashMap<>();
        if ("UP".equals(db.status())) {
            counts.put("scans", scanRepository.count());
            counts.put("datasets", datasetRepository.count());
            counts.put("preprocessingRuns", preprocessingRunRepository.count());
            counts.put("modelVersions", modelVersionRepository.count());
            counts.put("evaluationRuns", evaluationRunRepository.count());
        }

        String overall = "UP".equals(db.status()) ? ("UP".equals(ai.status()) ? "UP" : "DEGRADED") : "DOWN";
        return new HealthResponse(overall, "spring-boot-backend", Instant.now().toString(), db, ai, counts);
    }

    private DatabaseHealth checkDatabase() {
        try (Connection conn = dataSource.getConnection();
             Statement st = conn.createStatement();
             ResultSet rs = st.executeQuery(
                     "SELECT current_database() AS db, version() AS ver")) {
            if (rs.next()) {
                String version = rs.getString("ver");
                String shortVersion = version != null && version.contains(",")
                        ? version.substring(0, version.indexOf(','))
                        : version;
                return new DatabaseHealth("UP", rs.getString("db") + " (" + shortVersion + ")");
            }
            return new DatabaseHealth("DOWN", "No result from database");
        } catch (Exception ex) {
            return new DatabaseHealth("DOWN", ex.getClass().getSimpleName() + ": " + safeMessage(ex));
        }
    }

    private DatabaseHealth checkAiService() {
        try {
            Map<?, ?> body = aiClient.get()
                    .uri("/health")
                    .retrieve()
                    .body(Map.class);
            Object status = body == null ? null : body.get("status");
            return new DatabaseHealth("UP", aiBaseUrl + " -> " + status);
        } catch (Exception ex) {
            return new DatabaseHealth("DOWN", aiBaseUrl + " unreachable (" + ex.getClass().getSimpleName() + ")");
        }
    }

    private String safeMessage(Exception ex) {
        String msg = ex.getMessage();
        if (msg == null) {
            return "no message";
        }
        // Never leak credentials that JDBC sometimes embeds in messages.
        return msg.replaceAll("password[=:][^;,\\s]*", "password=***");
    }
}
