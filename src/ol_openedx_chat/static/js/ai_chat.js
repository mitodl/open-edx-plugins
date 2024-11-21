function AiChatAsideView(runtime, element, block_element, init_args) {
    console.log("INSIDE AiChatAsideView")
    const INITIAL_MESSAGES = [
      {
        content: "Hi! What are you interested in learning about?",
        role: "assistant",
      },
    ]

    const STARTERS = [
      { content: "I'm interested in quantum computing" },
      { content: "I want to understand global warming. " },
      { content: "I am curious about AI applications for business" },
    ]

    const REQUEST_OPTS = {
      apiUrl: "http://ai.open.odl.local:8002/http/recommendation_agent/",
      transformBody(messages) {
        const message = messages[messages.length - 1].content
        return { message }
      },
    }

    const el = document.getElementById("app-root")
    /**
     * Accepts all options of https://mitodl.github.io/smoot-design/?path=/docs/smoot-design-aichat--docs,\
     * plus root element
     */
    aiChat.aiChat({
      root: el,
      initialMessages: INITIAL_MESSAGES,
      conversationStarters: STARTERS,
      requestOpts: REQUEST_OPTS,
      className: "ai-chat",
    })
    console.log(init_args)
}
