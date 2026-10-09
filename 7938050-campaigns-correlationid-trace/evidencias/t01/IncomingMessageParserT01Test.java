package t01;

import co.com.bancolombia.dto.event.IncomingEventRequestDto;
import co.com.bancolombia.rabbit.handler.IncomingMessageParser;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.rabbitmq.client.AMQP;
import com.rabbitmq.client.Delivery;
import com.rabbitmq.client.Envelope;
import org.junit.jupiter.api.Test;
import org.reactivecommons.async.rabbit.RabbitMessage;

import java.nio.charset.StandardCharsets;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * T-01 paso 1 y 2: ¿IncomingMessageParser (real, sin modificar) tolera los campos
 * nuevos del body y los headers/props AMQP nuevos? ¿Respeta message_id explícito?
 */
class IncomingMessageParserT01Test {

    // Mismo ObjectMapper que InfrastructureConfig#objectMapper (sin el HandlerInstantiator de Spring)
    private final ObjectMapper mapper = new ObjectMapper()
            .disable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES);
    private final IncomingMessageParser parser = new IncomingMessageParser(mapper);

    private static final String DATA_COMMON = """
            "event_type":"notification","app_id":"APP01","datetime":"2026-10-08 10:00:00",
            "user_id":"user@corp.com","channel":"msteams",
            "notification_id":"11111111-1111-4111-8111-111111111111",
            "notification_node":"N-00-01","feedback_url":"http://campaigns/v1/retry","context":{"k":"v"}""";

    private RabbitMessage message(String data, Map<String, Object> headers, String messageId, String correlationId) {
        String body = "{\"eventId\":\"e-uuid\",\"name\":\"rk\",\"data\":{" + data + "}}";
        AMQP.BasicProperties props = new AMQP.BasicProperties.Builder()
                .headers(headers).messageId(messageId).correlationId(correlationId).build();
        return RabbitMessage.fromDelivery(new Delivery(new Envelope(1L, false, "ex", "rk"), props,
                body.getBytes(StandardCharsets.UTF_8)));
    }

    @Test
    void contratoActual_sinMessageId_usaNotificationIdComoMessageId() {
        IncomingEventRequestDto dto = parser.readValidatedEvent(
                message(DATA_COMMON, Map.of("x-consumer-id", "c1"), null, null));
        System.out.println("[T01-parser] actual -> messageId=" + dto.getMessageId() + " chatter=" + dto.getChatter());
        assertEquals("11111111-1111-4111-8111-111111111111", dto.getMessageId());
    }

    @Test
    void contratoNuevo_conMessageIdYCampaignId_yHeadersAmqpNuevos_noFalla() {
        String data = DATA_COMMON + """
                ,"message_id":"11111111-1111-4111-8111-111111111111",
                "campaign_id":"22222222-2222-4222-8222-222222222222\"""";
        Map<String, Object> headers = Map.of(
                "x-consumer-id", "c1",
                "CorrelationId", "11111111-1111-4111-8111-111111111111",
                "campaign_id", "22222222-2222-4222-8222-222222222222");
        IncomingEventRequestDto dto = parser.readValidatedEvent(message(data, headers,
                "11111111-1111-4111-8111-111111111111", "11111111-1111-4111-8111-111111111111"));
        System.out.println("[T01-parser] nuevo -> messageId=" + dto.getMessageId()
                + " notificationId=" + dto.getNotificationId() + " (campaign_id ignorado sin error)");
        assertEquals("11111111-1111-4111-8111-111111111111", dto.getMessageId());
    }

    @Test
    void messageIdExplicitoDistinto_tienePrioridadSobreNotificationId() {
        String data = DATA_COMMON + ",\"message_id\":\"otro-id\"";
        IncomingEventRequestDto dto = parser.readValidatedEvent(message(data, Map.of(), null, null));
        System.out.println("[T01-parser] distinto -> messageId=" + dto.getMessageId());
        assertEquals("otro-id", dto.getMessageId());
    }
}
