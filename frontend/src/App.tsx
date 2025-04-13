import { useEffect } from "react";

import { sessionState, useChatSession } from "@chainlit/react-client";
import { Playground } from "./components/playground";
import { useRecoilValue } from "recoil";

const userEnv = {};

function App() {
  const { connect } = useChatSession();
  const session = useRecoilValue(sessionState);
  useEffect(() => {
    if (session?.socket.connected) {
      return;
    }
    fetch("https://rxorchestration.rivalz.ai/custom-auth", {
      method: "POST",
      headers: {
      "Content-Type": "application/json"
      },
      body: JSON.stringify({
      project_id: "67b465519870d36dd0fd9818",
      project_name: "Qualoo"
      }),
      credentials: "include"
    }).then(() => {
        connect({
          userEnv
        });
      });
  }, [connect]);

  return (
    <>
      <div>
        <Playground />
      </div>
    </>
  );
}

export default App;
