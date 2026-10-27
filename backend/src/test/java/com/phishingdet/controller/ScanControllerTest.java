package com.phishingdet.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.phishingdet.exception.BadRequestException;
import com.phishingdet.exception.GlobalExceptionHandler;
import com.phishingdet.exception.ExternalServiceException;
import com.phishingdet.service.AiServiceClient;
import com.phishingdet.service.CurrentUserService;
import com.phishingdet.service.ScanService;
import com.phishingdet.service.StorageService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.validation.beanvalidation.LocalValidatorFactoryBean;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Controller tests for the four scan entry points.
 *
 * <p>The Python AI service and the database are mocked: what is verified here is
 * the contract Spring Boot owns - request validation, request shaping before
 * forwarding, correct delegation to the AI client, persistence of the result,
 * and honest failure codes when the AI service is unavailable. Detection
 * quality itself is tested in the Python test suite.</p>
 */
class ScanControllerTest {

    private ScanService scanService;
    private AiServiceClient aiServiceClient;
    private StorageService storageService;
    private CurrentUserService currentUserService;
    private MockMvc mvc;
    private final ObjectMapper mapper = new ObjectMapper();

    @BeforeEach
    void setUp() {
        scanService = mock(ScanService.class);
        aiServiceClient = mock(AiServiceClient.class);
        storageService = mock(StorageService.class);
        // Standalone MockMvc has no security filter chain: treat every request
        // as anonymous (owner = null), which is exactly the extension's case.
        currentUserService = mock(CurrentUserService.class);
        when(currentUserService.current()).thenReturn(java.util.Optional.empty());
        when(currentUserService.currentIdOrNull()).thenReturn(null);

        LocalValidatorFactoryBean validator = new LocalValidatorFactoryBean();
        validator.afterPropertiesSet();

        mvc = MockMvcBuilders
                .standaloneSetup(new ScanController(scanService, aiServiceClient, storageService,
                        currentUserService))
                .setControllerAdvice(new GlobalExceptionHandler())
                .setValidator(validator)
                .build();
    }

    /** A minimal, realistic AI-service payload. */
    private Map<String, Object> aiResult() {
        return Map.of(
                "submittedInput", "https://example.com",
                "classification", "LEGITIMATE",
                "riskLevel", "LOW",
                "riskScore", 0.1,
                "status", "COMPLETED",
                "modalities", List.of(),
                "evidence", List.of());
    }

    /** What ScanService.persist returns: the payload enriched with the row id. */
    private Map<String, Object> persisted() {
        Map<String, Object> out = new java.util.LinkedHashMap<>(aiResult());
        out.put("id", 7L);
        out.put("inputType", "WEBSITE");
        return out;
    }

    /* --------------------------- validation ------------------------------ */

    @Test
    void websiteScanRejectsBlankUrlWith400() throws Exception {
        mvc.perform(post("/api/scans/website")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isBadRequest());

        verify(aiServiceClient, never()).analyzeWebsite(anyMap());
    }

    @Test
    void smsScanRejectsBlankMessageWith400() throws Exception {
        mvc.perform(post("/api/scans/sms")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"sender\":\"VM-BANK\"}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void emailScanRejectsBlankBodyWith400() throws Exception {
        mvc.perform(post("/api/scans/email")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"subject\":\"hello\"}"))
                .andExpect(status().isBadRequest());
    }

    /* --------------------------- delegation ------------------------------ */

    @Test
    void websiteScanForwardsDefaultsAndReturnsPersistedResult() throws Exception {
        when(aiServiceClient.analyzeWebsite(anyMap())).thenReturn(aiResult());
        when(scanService.persist(eq("WEBSITE"), anyMap(), any())).thenReturn(persisted());

        mvc.perform(post("/api/scans/website")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"url\":\"https://example.com\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(7))
                .andExpect(jsonPath("$.classification").value("LEGITIMATE"));

        ArgumentCaptor<Map<String, Object>> captor = captor();
        verify(aiServiceClient).analyzeWebsite(captor.capture());
        // Fetch and render default to on: a URL-only verdict is not a webpage scan.
        assertThat(captor.getValue()).containsEntry("url", "https://example.com")
                .containsEntry("fetch", true)
                .containsEntry("render", true);
    }

    @Test
    void websiteScanHonoursExplicitFalseFlags() throws Exception {
        when(aiServiceClient.analyzeWebsite(anyMap())).thenReturn(aiResult());
        when(scanService.persist(anyString(), anyMap(), any())).thenReturn(persisted());

        mvc.perform(post("/api/scans/website")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"url\":\"https://example.com\",\"fetch\":false,\"render\":false}"))
                .andExpect(status().isOk());

        ArgumentCaptor<Map<String, Object>> captor = captor();
        verify(aiServiceClient).analyzeWebsite(captor.capture());
        assertThat(captor.getValue()).containsEntry("fetch", false).containsEntry("render", false);
    }

    @Test
    void smsScanDelegatesWithAnalyzeLinks() throws Exception {
        when(aiServiceClient.analyzeSms(anyMap())).thenReturn(aiResult());
        when(scanService.persist(eq("SMS"), anyMap(), any())).thenReturn(persisted());

        mvc.perform(post("/api/scans/sms")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"message\":\"URGENT: verify your account\",\"sender\":\"VM-BANK\"}"))
                .andExpect(status().isOk());

        ArgumentCaptor<Map<String, Object>> captor = captor();
        verify(aiServiceClient).analyzeSms(captor.capture());
        assertThat(captor.getValue())
                .containsEntry("message", "URGENT: verify your account")
                .containsEntry("sender", "VM-BANK")
                .containsEntry("analyzeLinks", true);
    }

    /* ---------------------------- dispatcher ----------------------------- */

    @Test
    void genericDispatcherRoutesWebsiteInputType() throws Exception {
        when(aiServiceClient.analyzeWebsite(anyMap())).thenReturn(aiResult());
        when(scanService.persist(eq("WEBSITE"), anyMap(), any())).thenReturn(persisted());

        mvc.perform(post("/api/scans")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"inputType\":\"website\",\"url\":\"https://example.com\"}"))
                .andExpect(status().isOk());

        verify(aiServiceClient).analyzeWebsite(anyMap());
    }

    @Test
    void genericDispatcherRejectsUnknownInputType() throws Exception {
        mvc.perform(post("/api/scans")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"inputType\":\"MOBILE\",\"url\":\"https://example.com\"}"))
                .andExpect(status().isBadRequest());

        verify(aiServiceClient, never()).analyzeWebsite(anyMap());
    }

    @Test
    void genericDispatcherRejectsQrWithGuidance() throws Exception {
        mvc.perform(post("/api/scans")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"inputType\":\"QR\"}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void genericDispatcherRequiresTheBranchField() throws Exception {
        mvc.perform(post("/api/scans")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"inputType\":\"WEBSITE\"}"))
                .andExpect(status().isBadRequest());

        verify(aiServiceClient, never()).analyzeWebsite(anyMap());
    }

    /* -------------------------------- QR --------------------------------- */

    @Test
    void qrScanStoresImageAndDelegates() throws Exception {
        MockMultipartFile file = new MockMultipartFile(
                "file", "qr.png", "image/png", new byte[] { (byte) 0x89, 'P', 'N', 'G' });
        when(storageService.saveImage(any())).thenReturn("img-1-qr.png");
        when(aiServiceClient.analyzeQr(anyMap())).thenReturn(aiResult());
        when(scanService.persist(eq("QR"), anyMap(), any())).thenReturn(persisted());

        mvc.perform(multipart("/api/scans/qr").file(file))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.storedFile").value("img-1-qr.png"));

        ArgumentCaptor<Map<String, Object>> captor = captor();
        verify(aiServiceClient).analyzeQr(captor.capture());
        assertThat(captor.getValue()).containsEntry("filePath", "img-1-qr.png");
    }

    @Test
    void qrScanRejectsNonImageUploadWith400() throws Exception {
        MockMultipartFile file = new MockMultipartFile(
                "file", "payload.exe", "application/octet-stream", new byte[] { 0x00 });
        when(storageService.saveImage(any())).thenThrow(
                new BadRequestException("Only image files are supported for QR scans."));

        mvc.perform(multipart("/api/scans/qr").file(file))
                .andExpect(status().isBadRequest());
    }

    /* --------------------------- honest failures ------------------------- */

    @Test
    void aiServiceUnreachableReturns503NotAFakeVerdict() throws Exception {
        when(aiServiceClient.analyzeWebsite(anyMap()))
                .thenThrow(new ExternalServiceException("Python AI service is not reachable", 503));

        mvc.perform(post("/api/scans/website")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"url\":\"https://example.com\"}"))
                .andExpect(status().isServiceUnavailable());

        verify(scanService, never()).persist(anyString(), anyMap(), any());
    }

    @Test
    void aiServiceValidationErrorIsForwardedAs400() throws Exception {
        when(aiServiceClient.analyzeWebsite(anyMap()))
                .thenThrow(new ExternalServiceException("url is not a valid http(s) URL", 400));

        mvc.perform(post("/api/scans/website")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"url\":\"https://example.com\"}"))
                .andExpect(status().isBadRequest());
    }

    @SuppressWarnings("unchecked")
    private ArgumentCaptor<Map<String, Object>> captor() {
        return ArgumentCaptor.forClass(Map.class);
    }
}
