package com.phishingdet.controller;

import com.phishingdet.dto.HealthResponse;
import com.phishingdet.service.HealthService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api")
public class HealthController {

    private final HealthService healthService;

    public HealthController(HealthService healthService) {
        this.healthService = healthService;
    }

    /** Liveness + dependency check used by the dashboard "System Health" page. */
    @GetMapping("/health")
    public HealthResponse health() {
        return healthService.health();
    }
}
