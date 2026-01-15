import { TopNavigation } from '@cloudscape-design/components';
import Chat from './components/Chat';

function App() {
  return (
    <div className="App" style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <TopNavigation
        identity={{
          href: "#",
          title: "Amazon Bedrock Chat Demo"
        }}
        utilities={[
          {
            type: "button",
            text: "Documentation",
            href: "https://docs.aws.amazon.com/bedrock/",
            external: true,
            externalIconAriaLabel: " (opens in a new tab)"
          }
        ]}
      />
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <Chat />
      </div>
    </div>
  );
}

export default App;
