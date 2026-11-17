# Asking a person for a time of day in a web form

A form that asks for an opening hour or a departure time looks like a solved problem and is not: the browser's own
control cannot follow an app's 12/24-hour setting, the segmented controls libraries ship test poorly, and no
lightweight component library ships the shape that tests well. Measured while building an event-hours editor,
2026-11-15.

## The native input cannot be switched

The native `<input type="time">` is drawn in the operating system's or browser's clock format. Chrome, Edge and
Firefox give no attribute to change it, and `lang` on the element has no effect. Chrome on Windows can also draw a
seconds segment when the system format has seconds. MDN gives `step` a default of 60, under which most browsers
draw no seconds; whether that wins over a system format with seconds was not confirmed. An app with its own
12/24-hour setting needs a control it renders itself.

## What tests well

Service teams reporting on GOV.UK's design-system tracker (issue 5888) found:

- separate hour and minute boxes confused people, some of whom typed a whole time into each; and one team found the
  native input too unpredictable on desktop, recalling Firefox asking for AM/PM, Chrome for 24-hour, and Safari
  refusing a colon and wanting `1330`;
- a single text field that accepts several formats tested well, especially when it played back what it understood;
- midnight and noon are where people disagree (`12:00`, `00`, `24`), and echoing the normalised time removes the
  doubt.

Calendar applications combine these: one text field that reads `9`, `9pm`, `930` or `21:30`, minutes defaulting
to `:00`, a list of times at a fixed interval while focused, and the normalised time written back on blur. Google
Calendar keeps the full list as you type and only moves the highlight; a generic combobox narrows the list instead,
which reads as broken for times (empty at `1`, two rows at `17`).

A segmented field (React Aria `TimeField`, Mantine `TimePicker`) shows `--:--` where an example belongs and will not
take a bare hour: Mantine documents that `onChange` fires only when every segment is filled.

## Which libraries ship the calendar shape

- **Fluent UI `TimePicker`** and **Atlassian `@atlaskit/datetime-picker`** do, but each brings its whole design
  system (provider, theme, styling engine). Fluent's default parser requires `:mm`, so a bare `9` needs a parser of
  your own. Atlassian's reads `9`, `9pm` and `930`, but its field takes typed times only with `timeIsEditable` set,
  which defaults to off.
- **React Aria, Radix, Headless UI, shadcn** ship none; the recipe is a combobox fed a list of times.
- **MUI, Ant Design** use segmented or column pickers.

So the light path is React Aria's `ComboBox` with `allowsCustomValue`, `menuTrigger="focus"`,
a controlled `inputValue`, `defaultFilter={() => true}`, and the item list emptied once the text differs from the
stored value, plus a parser of your own. On a 12-hour clock a bare hour is ambiguous; reading it as AM in an
opening field and PM in a closing one, with the normalised text shown on blur, makes the guess visible.

A field holding its own typed text also has to accept a value set from outside (a "copy to days below" action):
replace the text when the incoming value differs from what the text parses to, and leave it alone while the text
does not parse yet, or the copy never appears or a half-typed entry gets wiped.
