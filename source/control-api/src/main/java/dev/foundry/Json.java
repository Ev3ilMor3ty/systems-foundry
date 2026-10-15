package dev.foundry;

import com.google.gson.*;
import java.math.BigDecimal;

final class Json {
  static final Gson GSON =
      new GsonBuilder()
          .setStrictness(Strictness.STRICT)
          .serializeNulls()
          .disableHtmlEscaping()
          .create();

  static JsonObject object(String s) {
    var value = GSON.fromJson(s, JsonElement.class);
    if (value == null || !value.isJsonObject())
      throw new IllegalArgumentException("Expected a JSON object");
    return value.getAsJsonObject();
  }

  static String text(JsonObject o, String key, int max) {
    var v = o.get(key);
    if (v == null || !v.isJsonPrimitive() || !v.getAsJsonPrimitive().isString())
      throw new IllegalArgumentException("Missing string: " + key);
    var s = v.getAsString();
    if (s.isBlank() || s.length() > max || s.chars().anyMatch(c -> c < 32))
      throw new IllegalArgumentException("Invalid string: " + key);
    return s;
  }

  static long integer(JsonObject o, String key, long min, long max) {
    try {
      var v = o.get(key);
      if (v == null || !v.isJsonPrimitive() || !v.getAsJsonPrimitive().isNumber())
        throw new ArithmeticException();
      long n = new BigDecimal(v.getAsString()).longValueExact();
      if (n < min || n > max) throw new ArithmeticException();
      return n;
    } catch (ArithmeticException | NumberFormatException e) {
      throw new IllegalArgumentException(key + " must be an integer in " + min + ".." + max);
    }
  }

  static JsonObject obj(Object... pairs) {
    var o = new JsonObject();
    for (int i = 0; i < pairs.length; i += 2)
      o.add((String) pairs[i], GSON.toJsonTree(pairs[i + 1]));
    return o;
  }
}
