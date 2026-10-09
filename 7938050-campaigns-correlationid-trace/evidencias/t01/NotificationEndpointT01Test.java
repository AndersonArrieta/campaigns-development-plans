package t01;

import co.com.bancolombia.dto.event.IncomingEventRequestDto;
import co.com.bancolombia.service.NotificationEndpoint;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.web.reactive.function.client.WebClient;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.concurrent.atomic.AtomicReference;

/**
 * T-01 paso 3: ¿qué body envía realmente NotificationEndpoint.notifyCampaignReschedule (real, sin modificar)
 * a POST /v1/retry? Se usa un WebClient con codecs por defecto, igual que WebClientConfig de engine_nlp_ms.
 */
class NotificationEndpointT01Test {

    private HttpServer server;
    private final AtomicReference<String> receivedBody = new AtomicReference<>();
    private final AtomicReference<String> receivedContentType = new AtomicReference<>();

    @BeforeEach
    void start() throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/v1/retry", exchange -> {
            receivedBody.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            receivedContentType.set(exchange.getRequestHeaders().getFirst("Content-Type"));
            byte[] ok = "OK".getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(200, ok.length);
            exchange.getResponseBody().write(ok);
            exchange.close();
        });
        server.start();
    }

    @AfterEach
    void stop() {
        server.stop(0);
    }

    @Test
    void bodyRealEnviadoAlEndpointDeReintento() {
        IncomingEventRequestDto event = IncomingEventRequestDto.builder()
                .notificationId("11111111-1111-4111-8111-111111111111")
                .datetime("2026-10-08 10:00:00")
                .feedbackUrl("http://127.0.0.1:" + server.getAddress().getPort() + "/v1/retry")
                .build();
        event.setMessageId("11111111-1111-4111-8111-111111111111");
        event.setAppId("APP01");

        NotificationEndpoint endpoint = new NotificationEndpoint(WebClient.builder().build());
        Throwable error = null;
        try {
            endpoint.notifyCampaignReschedule(event).block(Duration.ofSeconds(15));
        } catch (Throwable t) {
            error = t;
        }

        System.out.println("[T01-feedback] error=" + (error == null ? "ninguno" : error.getClass().getName() + ": " + rootMessage(error)));
        System.out.println("[T01-feedback] body recibido por /v1/retry=" + receivedBody.get());
        System.out.println("[T01-feedback] content-type=" + receivedContentType.get());

        // Validación equivalente a platform_campaigns_ms Handler.isValidPayload (snake_case + formato datetime)
        String body = receivedBody.get();
        boolean aceptado = body != null
                && body.contains("\"notification_id\":\"11111111-1111-4111-8111-111111111111\"")
                && body.matches(".*\"datetime\":\"\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}\".*");
        System.out.println("[T01-feedback] ¿platform_campaigns_ms lo aceptaría? " + aceptado);
    }

    private static String rootMessage(Throwable t) {
        Throwable r = t;
        while (r.getCause() != null && r.getCause() != r) r = r.getCause();
        return r.getClass().getSimpleName() + ": " + r.getMessage();
    }
}
