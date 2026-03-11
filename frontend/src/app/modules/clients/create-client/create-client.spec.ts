import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CreateClient } from './create-client';

describe('CreateClient', () => {
  let component: CreateClient;
  let fixture: ComponentFixture<CreateClient>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CreateClient]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CreateClient);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
