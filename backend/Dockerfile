# =====================================================================
# Spring Boot backend - multi-stage build (Maven -> JRE).
# =====================================================================
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build

# Cache dependencies separately from sources. Retries + read timeouts keep
# flaky links from failing the build mid-download.
COPY pom.xml ./
RUN mvn -q -B -Dmaven.wagon.http.retryHandler.count=6 -Dmaven.wagon.rto=180000 dependency:go-offline

COPY src ./src
RUN mvn -q -B -DskipTests -Dmaven.wagon.http.retryHandler.count=6 -Dmaven.wagon.rto=180000 package

FROM eclipse-temurin:21-jre-jammy
WORKDIR /app

# curl is used only for the container healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /usr/sbin/nologin phish \
    && mkdir -p /app/uploads \
    && chown -R phish:phish /app

COPY --from=build /build/target/*.jar app.jar
USER phish

EXPOSE 8088

HEALTHCHECK --interval=15s --timeout=5s --start-period=45s --retries=6 \
    CMD curl -fsS http://127.0.0.1:8088/api/health || exit 1

ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75", "-jar", "app.jar"]
