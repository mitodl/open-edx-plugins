function OLChatBlock(runtime, element, init_args) {
    import("https://cdn.jsdelivr.net/npm/@mitodl/smoot-design@6.18.2/dist/bundles/aiChat.es.js").then(aiChat => {
        var studioRuntime = new window.StudioRuntime.v1();
        const requestOpts = {
            apiUrl: studioRuntime.handlerUrl(element, 'ol_chat'),
            feedbackApiUrl: init_args.chat_rating_url,
            transformBody: (messages, { problem_set_title }) => {
                return {
                    message: messages[messages.length - 1].content,
                    problem_set_title: problem_set_title,
                }
            },
            csrfHeaderName: "X-CSRFToken",
            csrfCookieName: "csrftoken",
        }
        aiChat.init(
            {
                requestOpts,
                entryScreenEnabled: false,
                askTimTitle: init_args.ask_tim_title,
                useMathJax: true,
                problemSetListUrl: init_args.problem_list_url,
                initialMessages: [
                    {
                        role: "assistant",
                        content: init_args.bot_initial_message,
                    },
                ],
                problemSetInitialMessages: [
                    {
                        role: "assistant",
                        content: init_args.problem_set_initial_message,
                    },
                ],

            },
            {
                container: document.getElementById(`ai-chat-container-${init_args.block_id}`),
            },
        )
    }).catch(error => {
        console.error("Failed to load module:", error);
    });
}
