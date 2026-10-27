package com.phishingdet.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.phishingdet.entity.Scan;
import com.phishingdet.entity.User;
import com.phishingdet.exception.ResourceNotFoundException;
import com.phishingdet.repository.EvidenceRepository;
import com.phishingdet.repository.ModalityResultRepository;
import com.phishingdet.repository.ScanRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.mockito.ArgumentCaptor;

import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Scan ownership rules:
 * a scan saved while signed in belongs to that account, anonymous saves belong
 * to nobody, other accounts' scans are reported as missing (404 - ids must not
 * be enumerable), and unattributed scans stay visible to signed-in users as
 * shared device scans.
 */
class ScanOwnershipTest {

    @TempDir
    Path tempDir;

    private ScanRepository scanRepository;
    private ModalityResultRepository modalityResultRepository;
    private EvidenceRepository evidenceRepository;
    private ScanService service;

    @BeforeEach
    void setUp() throws Exception {
        scanRepository = mock(ScanRepository.class);
        modalityResultRepository = mock(ModalityResultRepository.class);
        evidenceRepository = mock(EvidenceRepository.class);
        when(scanRepository.save(any(Scan.class))).thenAnswer(inv -> {
            Scan s = inv.getArgument(0);
            s.setId(7L);
            return s;
        });
        // toFull() falls back to these when the scan has no in-memory rows.
        when(modalityResultRepository.findByScanIdOrderByModality(any())).thenReturn(List.of());
        when(evidenceRepository.findByScanId(any())).thenReturn(List.of());

        StorageService storage = new StorageService(
                tempDir.toString(), tempDir.resolve("processed").toString());
        service = new ScanService(scanRepository, modalityResultRepository,
                evidenceRepository, new ObjectMapper(), storage);
    }

    private User user(long id, String name) {
        User u = new User();
        u.setId(id);
        u.setUsername(name);
        u.setEmail(name + "@example.com");
        u.setPasswordHash("$2a$fakefakefakefakefakefake");
        u.setRole(User.Role.USER);
        return u;
    }

    private Scan scanOwnedBy(User owner) {
        Scan s = new Scan();
        s.setId(7L);
        s.setSubmittedUrl("https://example.com");
        s.setUser(owner);
        return s;
    }

    private Map<String, Object> minimalPayload() {
        Map<String, Object> ai = new LinkedHashMap<>();
        ai.put("inputType", "WEBSITE");
        ai.put("submittedInput", "https://example.com");
        ai.put("status", "COMPLETED");
        ai.put("classification", "LEGITIMATE");
        ai.put("riskLevel", "LOW");
        ai.put("riskScore", 0.1);
        ai.put("modalities", List.of());
        ai.put("evidence", List.of());
        return ai;
    }

    @Test
    void persistAttachesTheSignedInOwner() {
        User alice = user(1L, "alice");

        service.persist("WEBSITE", minimalPayload(), alice);

        ArgumentCaptor<Scan> captor = ArgumentCaptor.forClass(Scan.class);
        verify(scanRepository).save(captor.capture());
        assertThat(captor.getValue().getUser()).isSameAs(alice);
    }

    @Test
    void anonymousPersistSavesAnUnattributedScan() {
        service.persist("WEBSITE", minimalPayload(), null);

        ArgumentCaptor<Scan> captor = ArgumentCaptor.forClass(Scan.class);
        verify(scanRepository).save(captor.capture());
        assertThat(captor.getValue().getUser()).isNull();
    }

    @Test
    void anotherAccountsScanIsReportedAsNotFound() {
        when(scanRepository.findById(7L)).thenReturn(Optional.of(scanOwnedBy(user(9L, "mallory"))));

        assertThatThrownBy(() -> service.get(7L, 1L))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining("not found");
    }

    @Test
    void ownScanIsVisible() {
        when(scanRepository.findById(7L)).thenReturn(Optional.of(scanOwnedBy(user(1L, "alice"))));

        assertThat(service.get(7L, 1L).id()).isEqualTo(7L);
    }

    @Test
    void unattributedScansAreVisibleToSignedInUsers() {
        when(scanRepository.findById(7L)).thenReturn(Optional.of(scanOwnedBy(null)));

        assertThat(service.get(7L, 1L).id()).isEqualTo(7L);
        // ...and to anonymous callers too (open API read for curl/debugging).
        assertThat(service.get(7L, null).id()).isEqualTo(7L);
    }

    @Test
    void evidenceOfAnotherAccountsScanIsHidden() {
        when(scanRepository.findById(7L)).thenReturn(Optional.of(scanOwnedBy(user(9L, "mallory"))));

        assertThatThrownBy(() -> service.evidence(7L, 1L))
                .isInstanceOf(ResourceNotFoundException.class);
    }
}
