package com.phishingdet.dto;

import java.util.Map;

/**
 * Response of GET /api/health.
 *
 * <p>{@code status} is "UP" only when the database is reachable;
 * the AI service is reported separately so a partially running system is
 * described accurately instead of failing outright.</p>
 */
public record HealthResponse(
        String status,
        String service,
        String timestamp,
        DatabaseHealth database,
        DatabaseHealth aiService,
        Map<String, Long> counts) {

    public record DatabaseHealth(String status, String detail) {}
}
