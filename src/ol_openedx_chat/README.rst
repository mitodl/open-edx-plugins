ol-openedx-chat
###############

An xBlock aside to add MIT Open Learning chat into xBlocks.


Purpose
*******

MIT's AI chatbot for Open edX

Setup
=====

For detailed installation instructions, please refer to the `plugin installation guide <../../docs#installation-guide>`_.

Installation required in:

* LMS
* Studio (CMS)

Configuration
=============

1. edx-platform configuration
-----------------------------

   ::


   Add the following configuration values to the config file in Open edX. For any release after Juniper, that config file is ``/edx/etc/lms.yml``. These should be added to the top level. **Ask a fellow developer or devops for these values.**

   .. code-block::


   LEARN_AI_API_URL: <LEARN_AI_API_URL>

2. Add database record
----------------------

- Create a record for the
``XBlockAsidesConfig`` model (LMS admin URL:
``/admin/lms_xblock/xblockasidesconfig/``).

- Create a record in the ``StudioConfig`` model (CMS admin URL:
``/admin/xblock_config/studioconfig/``).

3. In frontend-app-learning, Run the below in the shell inside the learning MFE folder:
  `npm pack @mitodl/smoot-design@^3.4.0`

  `tar -xvzf mitodl-smoot-design*.tgz`

  `mv package mitodl-smoot-design`

4. Create env.config.jsx in the frontend-app-learning and add the below code:

  .. code-block::
  import { getConfig } from '@edx/frontend-platform';

  import * as remoteAiChatDrawer from "./mitodl-smoot-design/dist/bundles/remoteAiChatDrawer.umd.js";

  remoteAiChatDrawer.init({
    messageOrigin: getConfig().LMS_BASE_URL,
    transformBody: messages => ({ message: messages[messages.length - 1].content }),
  })

  const config = {
    ...process.env,
  };

  export default config;

5. Now start learning MFE by `npm run dev`
6. Now enable the `ol_openedx_chat.ol_openedx_chat_enabled` waffle flag for a course at <LMS_URL>/admin/waffle_utils/waffleflagcourseoverridemodel/
7. AI Assistant will be enabled for this course.
8. In CMS, you will see a single checkbox to enable the AI Chat for a problem/video block
9. Enable it for a block and visit the LMS and you will see a chat button. Clicking on button should open chat drawer.

Documentation
=============

License
*******

The code in this repository is licensed under the AGPL 3.0 unless
otherwise noted.

Please see `LICENSE.txt <LICENSE.txt>`_ for details.
