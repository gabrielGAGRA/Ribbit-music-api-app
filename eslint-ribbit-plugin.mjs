// @ts-check

const ANGULAR_STATE_CALLEES = new Set([
  'signal',
  'computed',
  'linkedSignal',
  'resource',
  'rxResource',
  'toSignal',
  'inject',
]);

const DOM_EVENT_HANDLER_PATTERN =
  /^(?:on|handle)(?:[A-Z]\w*)?(?:Click|Change|Input|Submit|Keydown|KeyDown|KeyUp|KeyPress|Focus|Blur|MouseDown|MouseUp|PointerDown|PointerMove|PointerUp|PointerCancel)$/;

const ANGULAR_LIFECYCLE_HOOKS = new Set([
  'ngOnInit',
  'ngOnDestroy',
  'ngAfterViewInit',
  'ngAfterContentInit',
  'ngAfterViewChecked',
  'ngAfterContentChecked',
  'ngOnChanges',
  'ngDoCheck',
]);

function hasComponentDecorator(classNode) {
  const decorators = classNode.decorators ?? [];
  return decorators.some((decorator) => {
    const expr = decorator.expression;
    if (!expr) return false;
    if (expr.type === 'CallExpression' && expr.callee.type === 'Identifier') {
      return expr.callee.name === 'Component';
    }
    if (expr.type === 'Identifier') {
      return expr.name === 'Component';
    }
    return false;
  });
}

function getCalleeName(expr) {
  if (!expr || expr.type !== 'CallExpression') return null;
  if (expr.callee.type === 'Identifier') return expr.callee.name;
  return null;
}

function getPropertyName(prop) {
  if (prop.key.type === 'Identifier') return prop.key.name;
  if (prop.key.type === 'Literal') return String(prop.key.value);
  return 'member';
}

const componentMemberAccessibilityRule = {
  meta: {
    type: 'problem',
    docs: {
      description:
        'Require protected or private on component signal, computed, resource, toSignal, and inject fields.',
    },
    schema: [],
  },
  create(context) {
    return {
      ClassDeclaration(node) {
        if (!hasComponentDecorator(node)) return;
        for (const member of node.body.body) {
          if (member.static) continue;
          if (member.type === 'PropertyDefinition') {
            const calleeName = getCalleeName(member.value);
            if (!calleeName || !ANGULAR_STATE_CALLEES.has(calleeName)) continue;
            if (member.accessibility === 'protected' || member.accessibility === 'private') {
              continue;
            }
            context.report({
              node: member,
              message: `Component member '${getPropertyName(member)}' initialized with ${calleeName}() must be marked protected or private.`,
            });
          } else if (member.type === 'MethodDefinition') {
            if (member.kind === 'constructor') continue;
            const methodName = getPropertyName(member);
            if (ANGULAR_LIFECYCLE_HOOKS.has(methodName)) continue;
            if (member.accessibility === 'protected' || member.accessibility === 'private') {
              continue;
            }
            context.report({
              node: member,
              message: `Component method '${methodName}()' must be marked protected or private.`,
            });
          }
        }
      },
    };
  },
};

const requireAssertionCommentRule = {
  meta: {
    type: 'problem',
    docs: {
      description:
        'Require an explanatory comment on `as` type assertions (excluding `as const` and `as unknown`).',
    },
    schema: [],
  },
  create(context) {
    const sourceCode = context.sourceCode;
    return {
      TSAsExpression(node) {
        const annotation = node.typeAnnotation;
        if (annotation.type === 'TSUnknownKeyword') return;
        if (
          annotation.type === 'TSTypeReference' &&
          annotation.typeName.type === 'Identifier' &&
          annotation.typeName.name === 'const'
        ) {
          return;
        }

        if (
          sourceCode.getCommentsBefore(node).length > 0 ||
          sourceCode.getCommentsAfter(node).length > 0
        ) {
          return;
        }

        const startLine = node.loc.start.line;
        const endLine = node.loc.end.line;
        const hasAdjacentLineComment = sourceCode.getAllComments().some((comment) => {
          const commentEndLine = comment.loc.end.line;
          const commentStartLine = comment.loc.start.line;
          return (
            commentEndLine === startLine - 1 ||
            commentStartLine === startLine ||
            commentEndLine === endLine
          );
        });

        if (!hasAdjacentLineComment) {
          context.report({
            node,
            message:
              'Avoid `as` type assertions without a nearby comment explaining why the cast is safe; prefer runtime narrowing.',
          });
        }
      },
    };
  },
};

const noDomEventHandlerNamesRule = {
  meta: {
    type: 'suggestion',
    docs: {
      description:
        'Name component event handlers after the business action instead of the DOM trigger event.',
    },
    schema: [],
  },
  create(context) {
    return {
      ClassDeclaration(node) {
        if (!hasComponentDecorator(node)) return;
        for (const member of node.body.body) {
          if (member.type !== 'MethodDefinition' || member.key.type !== 'Identifier') continue;
          if (DOM_EVENT_HANDLER_PATTERN.test(member.key.name)) {
            context.report({
              node: member.key,
              message: `Rename '${member.key.name}' after the business action instead of the DOM event.`,
            });
          }
        }
      },
    };
  },
};

const SNAKE_CASE_PROPERTY_PATTERN = /^[a-z]+_[a-z_]+$/;

const noTemplateSnakeCaseRule = {
  meta: {
    type: 'problem',
    docs: {
      description: 'Disallow accessing raw backend snake_case properties in Angular templates.',
    },
    schema: [],
  },
  create(context) {
    return {
      PropertyRead(node) {
        if (typeof node.name === 'string' && SNAKE_CASE_PROPERTY_PATTERN.test(node.name)) {
          context.report({
            node,
            message: `Avoid raw snake_case property '${node.name}' in templates; map DTOs to camelCase in the data layer.`,
          });
        }
      },
    };
  },
};

export default {
  rules: {
    'component-member-accessibility': componentMemberAccessibilityRule,
    'require-assertion-comment': requireAssertionCommentRule,
    'no-dom-event-handler-names': noDomEventHandlerNamesRule,
    'no-template-snake-case': noTemplateSnakeCaseRule,
  },
};
