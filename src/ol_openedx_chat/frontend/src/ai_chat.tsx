////////////////////////////////////////////////////////////////////////////////
// Remember: changes in this file will only take effect when you run          //
// npm run build       or      npm run watch                                  //
////////////////////////////////////////////////////////////////////////////////
import React from 'react';
import ReactDOM from 'react-dom/client';
import { BoundRuntime } from './xblock-utils';

interface Props {
  runtime: BoundRuntime;
}

const StudentView: React.FC<Props> = ({ runtime, ...props }) => {

  return <div className="react_xblock_2_block">
      <h1>ReactXBlock8</h1>
    </div>
}

function initStudentView(runtime, container, BlockContainer, initData) {
  if ('jquery' in container) {
    // Fix inconsistent parameter typing:
    container = container[0];
  }
  console.log("HELLLLOOOOOOOOOOOOOOXXXXXXXXX")
  const domNode = document.getElementById('aside_root');
  console.log(domNode)
  const root = ReactDOM.createRoot(domNode);
  root.render(
      <StudentView runtime={new BoundRuntime(runtime, container)} />
  );
}

// We need to add our init function to the global (window) namespace, without conflicts:
(globalThis as any).initReactXBlock8StudentView = initStudentView;
