package dev.foundry;

import static org.junit.jupiter.api.Assertions.*;

import org.junit.jupiter.api.Test;

class ProofVerifierTest {
  static final String INPUT =
      "{\"workers\":1,\"tasks\":1,\"edges\":[{\"worker\":0,\"task\":0,\"cost\":7}]}";
  static final String SOLUTION =
      "{\"optimal\":{\"cardinality\":1,\"cost\":7,\"pairs\":[{\"worker\":0,\"task\":0,\"cost\":7}]},\"certificate\":{\"schema\":1,\"potential\":[-7,0,-7,0],\"source_side\":[2],\"cut_capacity\":1}}";

  @Test
  void acceptsPrimalAndDualWitnesses() {
    assertDoesNotThrow(() -> ProofVerifier.verify(Json.object(INPUT), Json.object(SOLUTION)));
  }

  @Test
  void rejectsWrongCostPotentialCutAndIneligibleEdge() {
    for (var change :
        new String[][] {
          {"\"cost\":7", "\"cost\":8"},
          {"[-7,0,-7,0]", "[0,0,0,0]"},
          {"[2]", "[2,3]"},
          {"\"task\":0", "\"task\":1"}
        }) {
      var wrong = SOLUTION.replace(change[0], change[1]);
      assertThrows(
          IllegalArgumentException.class,
          () -> ProofVerifier.verify(Json.object(INPUT), Json.object(wrong)));
    }
  }
}
