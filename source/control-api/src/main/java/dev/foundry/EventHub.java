package dev.foundry;

import com.google.gson.JsonObject;
import java.util.Set;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ConcurrentHashMap;

/** Each event is a full snapshot, so slow consumers can safely skip versions. */
final class EventHub {
  private final Set<ArrayBlockingQueue<String>> clients = ConcurrentHashMap.newKeySet();

  synchronized ArrayBlockingQueue<String> subscribe() {
    if (clients.size() >= 8) throw new IllegalStateException("Live connection limit reached");
    var q = new ArrayBlockingQueue<String>(4);
    clients.add(q);
    return q;
  }

  void remove(ArrayBlockingQueue<String> q) {
    clients.remove(q);
  }

  void publish(JsonObject snapshot) {
    String event = frame(snapshot);
    for (var q : clients)
      if (!q.offer(event)) {
        q.clear();
        q.offer(event);
      }
  }

  int size() {
    return clients.size();
  }

  static String frame(JsonObject s) {
    return "id: "
        + s.get("revision").getAsLong()
        + "\nevent: snapshot\ndata: "
        + Json.GSON.toJson(s)
        + "\n\n";
  }
}
