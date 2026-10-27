package com.phishingdet.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.phishingdet.dto.DatasetPreviewDto;
import com.phishingdet.exception.ExternalServiceException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.List;
import java.util.Map;

/**
 * Typed client for the Python AI service.
 *
 * <p>Spring Boot never reimplements detection or preprocessing logic - it
 * delegates to the Python service over HTTP and translates failures into
 * meaningful API errors.</p>
 */
@Component
public class AiServiceClient {

    private static final Logger log = LoggerFactory.getLogger(AiServiceClient.class);

    private final RestClient client;
    private final ObjectMapper mapper;
    private final String baseUrl;

    public AiServiceClient(@Value("${ai.service.base-url}") String baseUrl,
                           @Value("${ai.service.connect-timeout-ms}") int connectTimeoutMs,
                           @Value("${ai.service.read-timeout-ms}") int readTimeoutMs,
                           ObjectMapper mapper) {
        this.baseUrl = baseUrl;
        this.mapper = mapper;
        java.time.Duration connect = java.time.Duration.ofMillis(connectTimeoutMs);
        java.time.Duration read = java.time.Duration.ofMillis(readTimeoutMs);
        org.springframework.http.client.SimpleClientHttpRequestFactory factory =
                new org.springframework.http.client.SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(connect);
        factory.setReadTimeout(read);
        this.client = RestClient.builder()
                .baseUrl(baseUrl)
                .requestFactory(factory)
                .build();
    }

    public boolean isReachable() {
        try {
            client.get().uri("/health").retrieve().body(String.class);
            return true;
        } catch (Exception ex) {
            return false;
        }
    }

    public DatasetPreviewDto inspect(String relativePath, String targetColumn) {
        Map<String, Object> body = Map.of(
                "filePath", relativePath,
                "targetColumn", targetColumn == null ? "" : targetColumn);
        try {
            String json = client.post()
                    .uri("/datasets/inspect")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(body)
                    .retrieve()
                    .body(String.class);
            return mapper.readValue(json, DatasetPreviewDto.class);
        } catch (org.springframework.web.client.HttpClientErrorException ex) {
            throw new ExternalServiceException(parseDetail(ex.getResponseBodyAsString()), ex.getStatusCode().value());
        } catch (Exception ex) {
            log.error("AI service inspect call failed", ex);
            throw new ExternalServiceException(
                    "Python AI service is not reachable at " + baseUrl + " - start it with scripts/start-ai-service.ps1",
                    503);
        }
    }

    /**
     * Executes real preprocessing in Python and returns the full result payload.
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> preprocess(String relativePath, String targetColumn,
                                          Map<String, Object> options, String outputFilename) {
        java.util.LinkedHashMap<String, Object> body = new java.util.LinkedHashMap<>();
        body.put("filePath", relativePath);
        body.put("targetColumn", targetColumn);
        body.put("options", options);
        if (outputFilename != null && !outputFilename.isBlank()) {
            body.put("outputFilename", outputFilename);
        }
        try {
            String json = client.post()
                    .uri("/datasets/preprocess")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(body)
                    .retrieve()
                    .body(String.class);
            return mapper.readValue(json, new TypeReference<Map<String, Object>>() {});
        } catch (org.springframework.web.client.HttpClientErrorException ex) {
            throw new ExternalServiceException(parseDetail(ex.getResponseBodyAsString()), ex.getStatusCode().value());
        } catch (ExternalServiceException ex) {
            throw ex;
        } catch (Exception ex) {
            log.error("AI service preprocess call failed", ex);
            throw new ExternalServiceException(
                    "Python AI service is not reachable at " + baseUrl + " - start it with scripts/start-ai-service.ps1",
                    503);
        }
    }

    /**
     * Generic POST to an internal AI analysis endpoint ({@code /analyze/*}).
     * The AI service owns every detection decision; Spring Boot only forwards the
     * input and stores what comes back.
     */
    public Map<String, Object> analyze(String path, Object body) {
        try {
            String json = client.post()
                    .uri(path)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(body)
                    .retrieve()
                    .body(String.class);
            return mapper.readValue(json, new TypeReference<Map<String, Object>>() {});
        } catch (org.springframework.web.client.RestClientResponseException ex) {
            // The AI service answered with a 4xx/5xx. Propagate the machine's own
            // explanation; a 5xx is a bad gateway situation, not an outage.
            int code = ex.getStatusCode().value();
            String detail = parseDetail(ex.getResponseBodyAsString());
            if (code >= 500) {
                throw new ExternalServiceException(
                        "The AI service failed while processing this input: " + detail, 502);
            }
            throw new ExternalServiceException(detail, code);
        } catch (org.springframework.web.client.ResourceAccessException ex) {
            // Connection-level failure (service down / DNS / refused).
            log.error("AI service unreachable at {}: {}", baseUrl, ex.getMessage());
            throw new ExternalServiceException(
                    "Python AI service is not reachable at " + baseUrl
                            + " - start it with scripts/start-ai-service.ps1", 503);
        } catch (Exception ex) {
            log.error("AI service analysis call failed: {}", path, ex);
            throw new ExternalServiceException(
                    "Unexpected error while calling the AI service: " + ex.getMessage(), 502);
        }
    }

    public Map<String, Object> analyzeWebsite(Map<String, Object> body) {
        return analyze("/analyze/website", body);
    }

    public Map<String, Object> analyzeEmail(Map<String, Object> body) {
        return analyze("/analyze/email", body);
    }

    public Map<String, Object> analyzeSms(Map<String, Object> body) {
        return analyze("/analyze/sms", body);
    }

    public Map<String, Object> analyzeQr(Map<String, Object> body) {
        return analyze("/analyze/qr", body);
    }

    @SuppressWarnings("unchecked")
    private String parseDetail(String responseBody) {
        if (responseBody == null || responseBody.isBlank()) {
            return "AI service rejected the request.";
        }
        try {
            Map<String, Object> parsed = mapper.readValue(responseBody, Map.class);
            Object detail = parsed.get("detail");
            if (detail != null) {
                return String.valueOf(detail);
            }
        } catch (Exception ignored) {
            // fall through to generic message
        }
        return "AI service rejected the request.";
    }

    public List<Map<String, Object>> health() {
        try {
            String json = client.get().uri("/health").retrieve().body(String.class);
            return List.of(mapper.readValue(json, new TypeReference<Map<String, Object>>() {}));
        } catch (Exception ex) {
            return List.of(Map.of("status", "DOWN", "detail", baseUrl + " unreachable"));
        }
    }
}
